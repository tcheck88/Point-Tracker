/**
 * Check WhatsApp Session Status
 * Used by Flask to verify session on startup and display status
 *
 * Output: JSON with session status
 * Exit codes:
 *   0 = Has valid session
 *   1 = No session or error
 *   2 = Session exists but may need refresh
 */

const {
    createClient,
    restoreSessionFromDB,
    checkSessionExists,
    updateConnectionStatus,
    backupSessionToDB,
    pool
} = require('./whatsapp_client');

const TIMEOUT_MS = 30000; // 30 second timeout

async function checkSession() {
    // First check database
    const sessionInfo = await checkSessionExists();

    if (!sessionInfo.exists) {
        console.log(JSON.stringify({
            status: 'no_session',
            message: 'No WhatsApp session found. Please scan QR code.',
            needsSetup: true
        }));
        await pool.end();
        process.exit(1);
    }

    // Try to restore and verify session
    console.error('INFO: Found session in database, verifying...');
    const restored = await restoreSessionFromDB();

    if (!restored) {
        console.log(JSON.stringify({
            status: 'restore_failed',
            message: 'Failed to restore session from database.',
            needsSetup: true
        }));
        await pool.end();
        process.exit(1);
    }

    const client = createClient();
    let verified = false;

    // Set up timeout
    const timeoutId = setTimeout(async () => {
        if (!verified) {
            console.log(JSON.stringify({
                status: 'timeout',
                message: 'Session verification timed out. Session may still be valid.',
                needsSetup: false,
                lastConnected: sessionInfo.lastConnected
            }));
            await client.destroy().catch(() => {});
            await pool.end();
            process.exit(2);
        }
    }, TIMEOUT_MS);

    // Handle QR event (session expired)
    client.on('qr', async () => {
        clearTimeout(timeoutId);
        console.log(JSON.stringify({
            status: 'expired',
            message: 'Session expired. Please scan QR code again.',
            needsSetup: true
        }));
        await updateConnectionStatus(false);
        await client.destroy();
        await pool.end();
        process.exit(1);
    });

    // Handle ready event (session valid)
    client.on('ready', async () => {
        clearTimeout(timeoutId);
        verified = true;

        const info = client.info;
        console.log(JSON.stringify({
            status: 'valid',
            message: 'WhatsApp session is valid and connected.',
            needsSetup: false,
            phone: info?.wid?.user || 'unknown',
            platform: info?.platform || 'unknown',
            lastConnected: new Date().toISOString()
        }));

        await updateConnectionStatus(true);
        await backupSessionToDB();
        await client.destroy();
        await pool.end();
        process.exit(0);
    });

    // Handle auth failure
    client.on('auth_failure', async (msg) => {
        clearTimeout(timeoutId);
        console.log(JSON.stringify({
            status: 'auth_failed',
            message: `Authentication failed: ${msg}`,
            needsSetup: true
        }));
        await updateConnectionStatus(false);
        await client.destroy();
        await pool.end();
        process.exit(1);
    });

    // Initialize
    console.error('INFO: Verifying WhatsApp session...');
    try {
        await client.initialize();
    } catch (initErr) {
        clearTimeout(timeoutId);
        console.log(JSON.stringify({
            status: 'init_failed',
            message: `Initialization failed: ${initErr.message}`,
            needsSetup: true
        }));
        await pool.end();
        process.exit(1);
    }
}

checkSession();
