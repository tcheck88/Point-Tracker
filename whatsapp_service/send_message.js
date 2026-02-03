/**
 * Send WhatsApp Message Script
 * Called by Flask via subprocess: node send_message.js "+1234567890" "Hello World"
 *
 * Exit codes:
 *   0 = Success
 *   1 = Missing arguments
 *   2 = No session found (need to scan QR)
 *   3 = Session expired (need to re-scan QR)
 *   4 = Send failed
 *   5 = Connection timeout
 */

const {
    createClient,
    restoreSessionFromDB,
    backupSessionToDB,
    checkSessionExists,
    updateConnectionStatus,
    clearSessionFromDB,
    pool
} = require('./whatsapp_client');

const TIMEOUT_MS = 60000; // 60 second timeout for connection

async function sendMessage(phoneNumber, message) {
    // Validate arguments
    if (!phoneNumber || !message) {
        console.error('Usage: node send_message.js <phone_number> <message>');
        console.error('Phone number should be in E.164 format (e.g., +15551234567)');
        process.exit(1);
    }

    // Clean phone number - remove any non-digit except leading +
    let cleanNumber = phoneNumber.replace(/[^\d+]/g, '');
    if (cleanNumber.startsWith('+')) {
        cleanNumber = cleanNumber.substring(1);
    }

    // WhatsApp format: number@c.us
    const chatId = `${cleanNumber}@c.us`;

    console.log(`Preparing to send message to ${chatId}`);

    // Check if session exists
    const sessionInfo = await checkSessionExists();
    if (!sessionInfo.exists) {
        console.error('ERROR: No WhatsApp session found. Please scan QR code first.');
        console.error('Visit /admin/whatsapp-setup to link your WhatsApp account.');
        process.exit(2);
    }

    // Restore session from database
    const restored = await restoreSessionFromDB();
    if (!restored) {
        console.error('ERROR: Failed to restore session from database.');
        process.exit(2);
    }

    const client = createClient();
    let connected = false;
    let messageSent = false;

    // Set up timeout
    const timeoutId = setTimeout(async () => {
        if (!connected) {
            console.error('ERROR: Connection timeout');
            await updateConnectionStatus(false);
            await pool.end();
            process.exit(5);
        }
    }, TIMEOUT_MS);

    // Handle QR event (session expired)
    client.on('qr', async () => {
        clearTimeout(timeoutId);
        console.error('ERROR: Session expired. QR code required.');
        console.error('Please visit /admin/whatsapp-setup to re-link your WhatsApp account.');
        await clearSessionFromDB();
        await updateConnectionStatus(false);
        await client.destroy();
        await pool.end();
        process.exit(3);
    });

    // Handle authentication failure
    client.on('auth_failure', async (msg) => {
        clearTimeout(timeoutId);
        console.error('ERROR: Authentication failed:', msg);
        await clearSessionFromDB();
        await updateConnectionStatus(false);
        await client.destroy();
        await pool.end();
        process.exit(3);
    });

    // Handle ready event
    client.on('ready', async () => {
        clearTimeout(timeoutId);
        connected = true;
        console.log('WhatsApp client connected');

        try {
            // Send the message
            await client.sendMessage(chatId, message);
            console.log(`SUCCESS: Message sent to ${phoneNumber}`);
            messageSent = true;

            // Update status and backup session
            await updateConnectionStatus(true);
            await backupSessionToDB();

        } catch (sendErr) {
            console.error('ERROR: Failed to send message:', sendErr.message);
        }

        // Cleanup
        await client.destroy();
        await pool.end();
        process.exit(messageSent ? 0 : 4);
    });

    // Handle disconnection
    client.on('disconnected', async (reason) => {
        console.log('Client disconnected:', reason);
        await updateConnectionStatus(false);
    });

    // Initialize client
    console.log('Initializing WhatsApp client...');
    try {
        await client.initialize();
    } catch (initErr) {
        clearTimeout(timeoutId);
        console.error('ERROR: Failed to initialize client:', initErr.message);
        await pool.end();
        process.exit(4);
    }
}

// Get arguments and run
const args = process.argv.slice(2);
sendMessage(args[0], args[1]);
