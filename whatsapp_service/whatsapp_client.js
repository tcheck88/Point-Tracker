/**
 * WhatsApp Client Module for Point-Tracker
 * Handles session persistence via Supabase PostgreSQL
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const { Pool } = require('pg');
const fs = require('fs');
const path = require('path');

// Database connection using same env vars as Flask app
const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_URL?.includes('sslmode=require') ? { rejectUnauthorized: false } : false
});

const SESSION_ID = 'default';
const LOCAL_SESSION_PATH = path.join(__dirname, '.wwebjs_auth');

/**
 * Load session data from Supabase
 */
async function loadSessionFromDB() {
    try {
        const result = await pool.query(
            'SELECT session_data FROM whatsapp_session WHERE session_id = $1',
            [SESSION_ID]
        );
        if (result.rows.length > 0 && result.rows[0].session_data) {
            return JSON.parse(result.rows[0].session_data);
        }
    } catch (err) {
        console.error('Error loading session from DB:', err.message);
    }
    return null;
}

/**
 * Save session data to Supabase
 */
async function saveSessionToDB(sessionData) {
    try {
        const jsonData = JSON.stringify(sessionData);
        await pool.query(`
            INSERT INTO whatsapp_session (session_id, session_data, is_connected, updated_at)
            VALUES ($1, $2, true, CURRENT_TIMESTAMP)
            ON CONFLICT (session_id)
            DO UPDATE SET session_data = $2, is_connected = true, updated_at = CURRENT_TIMESTAMP
        `, [SESSION_ID, jsonData]);
        console.log('Session saved to database');
    } catch (err) {
        console.error('Error saving session to DB:', err.message);
    }
}

/**
 * Update connection status in database
 */
async function updateConnectionStatus(isConnected) {
    try {
        await pool.query(`
            UPDATE whatsapp_session
            SET is_connected = $1,
                last_connected_at = CASE WHEN $1 = true THEN CURRENT_TIMESTAMP ELSE last_connected_at END,
                updated_at = CURRENT_TIMESTAMP
            WHERE session_id = $2
        `, [isConnected, SESSION_ID]);
    } catch (err) {
        console.error('Error updating connection status:', err.message);
    }
}

/**
 * Clear session from database (used when session is invalid)
 */
async function clearSessionFromDB() {
    try {
        await pool.query(`
            UPDATE whatsapp_session
            SET session_data = NULL, is_connected = false, updated_at = CURRENT_TIMESTAMP
            WHERE session_id = $1
        `, [SESSION_ID]);
        console.log('Session cleared from database');
    } catch (err) {
        console.error('Error clearing session from DB:', err.message);
    }
}

/**
 * Check if we have a valid session in the database
 */
async function checkSessionExists() {
    try {
        const result = await pool.query(
            'SELECT session_data, is_connected, last_connected_at FROM whatsapp_session WHERE session_id = $1',
            [SESSION_ID]
        );
        if (result.rows.length > 0 && result.rows[0].session_data) {
            return {
                exists: true,
                isConnected: result.rows[0].is_connected,
                lastConnected: result.rows[0].last_connected_at
            };
        }
    } catch (err) {
        console.error('Error checking session:', err.message);
    }
    return { exists: false, isConnected: false, lastConnected: null };
}

/**
 * Find Chrome executable - checks Render's persistent cache first
 */
function findChromePath() {
    const possiblePaths = [
        // Render persistent cache (set during build)
        '/opt/render/project/src/.puppeteer/chrome/linux-*/chrome-linux64/chrome',
        // Default Puppeteer cache locations
        '/opt/render/.cache/puppeteer/chrome/linux-*/chrome-linux64/chrome',
        process.env.PUPPETEER_EXECUTABLE_PATH,
    ].filter(Boolean);

    const glob = require('path');
    const fs = require('fs');

    // Check Render persistent location first
    const renderCacheBase = '/opt/render/project/src/.puppeteer/chrome';
    if (fs.existsSync(renderCacheBase)) {
        try {
            const versions = fs.readdirSync(renderCacheBase);
            for (const version of versions) {
                const chromePath = path.join(renderCacheBase, version, 'chrome-linux64', 'chrome');
                if (fs.existsSync(chromePath)) {
                    console.error('INFO: Found Chrome at:', chromePath);
                    return chromePath;
                }
            }
        } catch (e) {
            console.error('WARN: Error searching for Chrome:', e.message);
        }
    }

    // Fall back to default Puppeteer cache
    const defaultCacheBase = '/opt/render/.cache/puppeteer/chrome';
    if (fs.existsSync(defaultCacheBase)) {
        try {
            const versions = fs.readdirSync(defaultCacheBase);
            for (const version of versions) {
                const chromePath = path.join(defaultCacheBase, version, 'chrome-linux64', 'chrome');
                if (fs.existsSync(chromePath)) {
                    console.error('INFO: Found Chrome at:', chromePath);
                    return chromePath;
                }
            }
        } catch (e) {
            console.error('WARN: Error searching for Chrome:', e.message);
        }
    }

    // Let Puppeteer find it automatically
    console.error('INFO: No Chrome found in known paths, letting Puppeteer auto-detect');
    return undefined;
}

/**
 * Create a WhatsApp client with session restoration support
 */
function createClient() {
    const executablePath = findChromePath();

    const puppeteerConfig = {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    };

    // Only set executablePath if we found one
    if (executablePath) {
        puppeteerConfig.executablePath = executablePath;
    }

    const client = new Client({
        authStrategy: new LocalAuth({
            dataPath: LOCAL_SESSION_PATH
        }),
        puppeteer: puppeteerConfig
    });

    return client;
}

/**
 * Restore session from database to local storage
 */
async function restoreSessionFromDB() {
    const sessionData = await loadSessionFromDB();
    if (sessionData) {
        // Ensure directory exists
        if (!fs.existsSync(LOCAL_SESSION_PATH)) {
            fs.mkdirSync(LOCAL_SESSION_PATH, { recursive: true });
        }

        // Write session files
        const sessionDir = path.join(LOCAL_SESSION_PATH, `session-${SESSION_ID}`);
        if (!fs.existsSync(sessionDir)) {
            fs.mkdirSync(sessionDir, { recursive: true });
        }

        // Write the session data files
        for (const [filename, content] of Object.entries(sessionData)) {
            const filePath = path.join(sessionDir, filename);
            if (typeof content === 'object') {
                fs.writeFileSync(filePath, JSON.stringify(content));
            } else {
                fs.writeFileSync(filePath, content);
            }
        }

        console.log('Session restored from database');
        return true;
    }
    return false;
}

/**
 * Backup local session to database
 */
async function backupSessionToDB() {
    const sessionDir = path.join(LOCAL_SESSION_PATH, `session-${SESSION_ID}`);

    if (!fs.existsSync(sessionDir)) {
        console.log('No local session to backup');
        return false;
    }

    try {
        const sessionData = {};
        const files = fs.readdirSync(sessionDir);

        for (const file of files) {
            const filePath = path.join(sessionDir, file);
            const stat = fs.statSync(filePath);

            if (stat.isFile()) {
                const content = fs.readFileSync(filePath, 'utf8');
                try {
                    sessionData[file] = JSON.parse(content);
                } catch {
                    sessionData[file] = content;
                }
            }
        }

        await saveSessionToDB(sessionData);
        return true;
    } catch (err) {
        console.error('Error backing up session:', err.message);
        return false;
    }
}

module.exports = {
    pool,
    createClient,
    loadSessionFromDB,
    saveSessionToDB,
    clearSessionFromDB,
    checkSessionExists,
    updateConnectionStatus,
    restoreSessionFromDB,
    backupSessionToDB,
    SESSION_ID,
    LOCAL_SESSION_PATH
};
