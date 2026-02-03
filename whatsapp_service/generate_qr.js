/**
 * Generate QR Code for WhatsApp Linking
 * Called by Flask to display QR code on admin setup page
 *
 * Output modes:
 *   node generate_qr.js terminal  - Display QR in terminal (for testing)
 *   node generate_qr.js base64    - Output base64 PNG data (for web display)
 *   node generate_qr.js status    - Just check current status
 *
 * Exit codes:
 *   0 = Success (QR generated or already authenticated)
 *   1 = Error
 */

const {
    createClient,
    restoreSessionFromDB,
    backupSessionToDB,
    checkSessionExists,
    updateConnectionStatus,
    pool,
    LOCAL_SESSION_PATH
} = require('./whatsapp_client');

const qrcode = require('qrcode');
const qrcodeTerminal = require('qrcode-terminal');
const fs = require('fs');

const TIMEOUT_MS = 120000; // 2 minute timeout for QR scanning

async function generateQR(mode = 'base64') {
    // Check current session status
    if (mode === 'status') {
        const sessionInfo = await checkSessionExists();
        console.log(JSON.stringify({
            hasSession: sessionInfo.exists,
            isConnected: sessionInfo.isConnected,
            lastConnected: sessionInfo.lastConnected
        }));
        await pool.end();
        process.exit(0);
    }

    // Try to restore existing session first
    const sessionInfo = await checkSessionExists();
    if (sessionInfo.exists) {
        console.error('INFO: Existing session found, attempting to restore...');
        await restoreSessionFromDB();
    }

    // Clear any existing local session for fresh QR
    if (mode !== 'restore' && fs.existsSync(LOCAL_SESSION_PATH)) {
        fs.rmSync(LOCAL_SESSION_PATH, { recursive: true, force: true });
        console.error('INFO: Cleared local session for fresh QR');
    }

    const client = createClient();
    let qrGenerated = false;
    let authenticated = false;

    // Set up timeout
    const timeoutId = setTimeout(async () => {
        if (!authenticated) {
            console.error('ERROR: QR scan timeout');
            await client.destroy();
            await pool.end();
            process.exit(1);
        }
    }, TIMEOUT_MS);

    // Handle QR code generation
    client.on('qr', async (qr) => {
        qrGenerated = true;

        if (mode === 'terminal') {
            console.error('\nScan this QR code with WhatsApp:\n');
            qrcodeTerminal.generate(qr, { small: true });
            console.error('\nWaiting for scan...\n');
        } else if (mode === 'base64') {
            // Generate base64 PNG for web display
            try {
                const qrDataUrl = await qrcode.toDataURL(qr, {
                    width: 300,
                    margin: 2,
                    color: {
                        dark: '#000000',
                        light: '#ffffff'
                    }
                });
                // Output just the base64 data (remove data:image/png;base64, prefix for cleaner handling)
                console.log(JSON.stringify({
                    status: 'qr_ready',
                    qr_data: qrDataUrl
                }));
            } catch (err) {
                console.error('ERROR: Failed to generate QR image:', err.message);
            }
        }
    });

    // Handle successful authentication
    client.on('authenticated', async () => {
        console.error('INFO: WhatsApp authenticated successfully');
    });

    // Handle ready event (fully connected)
    client.on('ready', async () => {
        clearTimeout(timeoutId);
        authenticated = true;
        console.error('INFO: WhatsApp client ready');

        // Save session to database
        await backupSessionToDB();
        await updateConnectionStatus(true);

        // Get connected phone info
        const info = client.info;
        console.log(JSON.stringify({
            status: 'connected',
            phone: info?.wid?.user || 'unknown',
            platform: info?.platform || 'unknown'
        }));

        await client.destroy();
        await pool.end();
        process.exit(0);
    });

    // Handle auth failure
    client.on('auth_failure', async (msg) => {
        clearTimeout(timeoutId);
        console.error('ERROR: Authentication failed:', msg);
        await client.destroy();
        await pool.end();
        process.exit(1);
    });

    // Initialize client
    console.error('INFO: Initializing WhatsApp client for QR generation...');
    try {
        await client.initialize();
    } catch (initErr) {
        clearTimeout(timeoutId);
        console.error('ERROR: Failed to initialize:', initErr.message);
        await pool.end();
        process.exit(1);
    }
}

// Get mode from arguments
const mode = process.argv[2] || 'base64';
generateQR(mode);
