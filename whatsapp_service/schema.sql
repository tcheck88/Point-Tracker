-- WhatsApp Session Storage for Point-Tracker
-- Run this in Supabase SQL Editor

-- Table to store WhatsApp Web session credentials
CREATE TABLE IF NOT EXISTS whatsapp_session (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(50) DEFAULT 'default',
    session_data TEXT,  -- JSON blob containing auth credentials
    is_connected BOOLEAN DEFAULT FALSE,
    last_connected_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ensure only one session per session_id
CREATE UNIQUE INDEX IF NOT EXISTS idx_whatsapp_session_id ON whatsapp_session(session_id);

-- Add system_settings entries for WhatsApp configuration
-- (Run these INSERT statements, they'll be ignored if keys already exist)

INSERT INTO system_settings (setting_key, setting_value, description)
VALUES ('ENABLE_WHATSAPP_AUTOMATION', 'false', 'Master switch for WhatsApp automation (true/false)')
ON CONFLICT (setting_key) DO NOTHING;

INSERT INTO system_settings (setting_key, setting_value, description)
VALUES ('WHATSAPP_SENDER_NUMBER', '', 'The phone number linked to WhatsApp (E.164 format, e.g., +15551234567)')
ON CONFLICT (setting_key) DO NOTHING;

INSERT INTO system_settings (setting_key, setting_value, description)
VALUES ('WHATSAPP_RECIPIENT_NUMBERS', '', 'Comma-separated list of recipient numbers for alerts')
ON CONFLICT (setting_key) DO NOTHING;
