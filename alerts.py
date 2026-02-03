"""
alerts.py - Leer México Alert System
Updated: Supports SendGrid, Twilio SMS, Email-to-SMS (Gateway), AND WhatsApp
"""
import os
import json
import logging
import threading
import time
import base64
import http.client
from datetime import datetime
from db_utils import get_db_connection 
from twilio.rest import Client as TwilioClient

logger = logging.getLogger(__name__)

# Config
COOLDOWN_SECONDS = 5 
_last_alert_time = 0 

def _log_to_db(action_type, details):
    """Helper to write directly to audit_log."""
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO audit_log (action_type, details, recorded_by, event_time)
                VALUES (%s, %s, %s, %s)
            """, (action_type, details, "system_alerts", datetime.now()))
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"[{datetime.now()}] Failed to write to audit log: {e}")

# --- CONFIG CHECKS ---
def _check_sms_enabled():
    """Returns True if Twilio SMS is enabled."""
    try:
        conn = get_db_connection()
        if not conn: return False
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'ENABLE_SMS_FOR_ADMIN_MESSAGES'")
        row = cur.fetchone()
        conn.close()
        if row:
            val = row['setting_value'] if isinstance(row, dict) else row[0]
            return str(val).lower() in ('true', '1', 'yes', 'on')
        return False
    except Exception as e:
        logger.error(f"Error checking SMS config: {e}")
        return False

def _check_email_sms_enabled():
    """Returns True if Email-to-SMS (Gateway) is enabled."""
    try:
        conn = get_db_connection()
        if not conn: return False
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'ENABLE_EMAIL_TO_SMS'")
        row = cur.fetchone()
        conn.close()
        if row:
            val = row['setting_value'] if isinstance(row, dict) else row[0]
            return str(val).lower() in ('true', '1', 'yes', 'on')
        return False
    except Exception as e:
        logger.error(f"Error checking Email-SMS config: {e}")
        return False

def _check_whatsapp_enabled():
    """Returns True if WhatsApp messaging is enabled."""
    try:
        conn = get_db_connection()
        if not conn: return False
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'ENABLE_WHATSAPP'")
        row = cur.fetchone()
        conn.close()
        if row:
            val = row['setting_value'] if isinstance(row, dict) else row[0]
            return str(val).lower() in ('true', '1', 'yes', 'on')
        return False
    except Exception as e:
        logger.error(f"Error checking WhatsApp config: {e}")
        return False

# --- SENDING LOGIC ---

def _send_via_twilio(body, to_numbers):
    # ... (Your existing Twilio Logic - UNCHANGED) ...
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_PHONE_NUMBER')

    if not all([account_sid, auth_token, from_number]):
        _log_to_db("SMS_SKIPPED", "Missing Twilio credentials")
        return

    try:
        client = TwilioClient(account_sid, auth_token)
        for number in to_numbers:
            clean_number = number.strip()
            if not clean_number: continue
            try:
                message = client.messages.create(body=body, from_=from_number, to=clean_number)
                _log_to_db("SMS_SENT", f"SID: {message.sid} To: {clean_number}")
            except Exception as inner_e:
                logger.error(f"Failed to send to {clean_number}: {inner_e}")
                _log_to_db("SMS_FAILED_INDIVIDUAL", f"To: {clean_number} Error: {str(inner_e)}")
    except Exception as e:
        logger.error(f"Twilio Client Error: {e}")
        _log_to_db("SMS_FAILED_GLOBAL", str(e))

def _send_via_sendgrid(subject, message, to_emails, attachment_name, attachment_data, log_label="EMAIL"):
    # ... (Your existing SendGrid Logic - Minor update to support 'log_label') ...
    api_key = os.getenv('SENDGRID_API_KEY')
    sender_email = os.getenv('MAIL_USERNAME') 
    
    if not api_key:
        _log_to_db(f"{log_label}_CONFIG_ERROR", "Missing SENDGRID_API_KEY")
        return

    personalizations = [{"to": [{"email": email}]} for email in to_emails]
    
    # ... (Attachment logic unchanged) ...
    attachments_json = []
    if attachment_name and attachment_data:
        encoded_data = base64.b64encode(attachment_data).decode('utf-8')
        attachments_json.append({
            "content": encoded_data,
            "filename": attachment_name,
            "type": "text/csv", 
            "disposition": "attachment"
        })

    payload = {
        "personalizations": personalizations,
        "from": {"email": sender_email},
        "subject": subject,
        # Detect if this is SMS (plain text) or Email (HTML)
        "content": [{"type": "text/plain" if log_label == "SMS_GATEWAY" else "text/html", "value": message}]
    }
    
    if attachments_json: payload["attachments"] = attachments_json

    try:
        conn = http.client.HTTPSConnection("api.sendgrid.com")
        headers = {'Authorization': f"Bearer {api_key}", 'Content-Type': 'application/json'}
        conn.request("POST", "/v3/mail/send", json.dumps(payload), headers)
        res = conn.getresponse()
        
        if res.status in [200, 201, 202]:
            _log_to_db(f"{log_label}_SENT", f"To: {to_emails}")
        else:
            _log_to_db(f"{log_label}_FAILED", f"Status: {res.status}")
    except Exception as e:
        _log_to_db(f"{log_label}_FAILED", f"API Error: {str(e)}")

def _send_via_whatsapp(body, to_numbers):
    """
    Send WhatsApp messages using Twilio's WhatsApp Business API.
    Uses the same Twilio credentials as SMS but with 'whatsapp:' prefix.

    Requirements:
    - TWILIO_WHATSAPP_NUMBER env var (e.g., 'whatsapp:+14155238886' for sandbox)
    - Recipients must have joined the sandbox (for testing) or be approved contacts
    """
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    # WhatsApp sender number - could be sandbox or approved business number
    from_number = os.getenv('TWILIO_WHATSAPP_NUMBER')

    # Fallback to sandbox number if not configured
    if not from_number:
        from_number = 'whatsapp:+14155238886'  # Twilio's default sandbox number

    if not all([account_sid, auth_token]):
        _log_to_db("WHATSAPP_SKIPPED", "Missing Twilio credentials")
        return

    try:
        client = TwilioClient(account_sid, auth_token)
        for number in to_numbers:
            clean_number = number.strip()
            if not clean_number:
                continue

            # Ensure the 'whatsapp:' prefix is present
            if not clean_number.startswith('whatsapp:'):
                clean_number = f'whatsapp:{clean_number}'

            try:
                message = client.messages.create(
                    body=body,
                    from_=from_number,
                    to=clean_number
                )
                _log_to_db("WHATSAPP_SENT", f"SID: {message.sid} To: {clean_number}")
            except Exception as inner_e:
                error_msg = str(inner_e)
                logger.error(f"Failed to send WhatsApp to {clean_number}: {inner_e}")
                _log_to_db("WHATSAPP_FAILED_INDIVIDUAL", f"To: {clean_number} Error: {error_msg}")
    except Exception as e:
        logger.error(f"Twilio WhatsApp Client Error: {e}")
        _log_to_db("WHATSAPP_FAILED_GLOBAL", str(e))

# --- PUBLIC FUNCTIONS ---

def send_sms(message_body, to_numbers=None):
    """Twilio SMS Trigger"""
    if not _check_sms_enabled(): return False
    if not to_numbers: return False

    sms_thread = threading.Thread(target=_send_via_twilio, args=(message_body, to_numbers))
    sms_thread.daemon = True
    sms_thread.start()
    return True

def send_email_sms(message_body, recipient_gateways=None):
    """Email-to-SMS Gateway Trigger (NEW)"""
    if not _check_email_sms_enabled(): return False
    if not recipient_gateways: return False

    # Short subject for SMS
    sms_subject = "Alert"
    
    # We use "SMS_GATEWAY" label to differentiate logs
    sms_thread = threading.Thread(
        target=_send_via_sendgrid,
        args=(sms_subject, message_body, recipient_gateways, None, None, "SMS_GATEWAY")
    )
    sms_thread.daemon = True
    sms_thread.start()
    return True

def send_alert(subject, message, error_obj=None, to_emails=None, attachment_name=None, attachment_data=None):
    """Standard Email Trigger"""
    global _last_alert_time
    if not attachment_name:
        if (time.time() - _last_alert_time) < COOLDOWN_SECONDS: return False
        _last_alert_time = time.time()
        
    recipients = []
    if to_emails: recipients = [e.strip() for e in to_emails if e.strip()]
    if not recipients:
        default = os.getenv('ADMIN_EMAIL')
        if default: recipients = [default]
    if not recipients: return False

    email_thread = threading.Thread(
        target=_send_via_sendgrid,
        args=(subject, message, recipients, attachment_name, attachment_data, "EMAIL")
    )
    email_thread.daemon = True
    email_thread.start()
    return True

def send_whatsapp(message_body, to_numbers=None):
    """
    WhatsApp Trigger via Twilio WhatsApp Business API.

    Phone numbers can be stored with or without the 'whatsapp:' prefix.
    E.g., '+15551234567' or 'whatsapp:+15551234567' both work.

    For Sandbox testing, recipients must first join by sending:
    'join <your-sandbox-code>' to Twilio's WhatsApp sandbox number.
    """
    if not _check_whatsapp_enabled():
        return False
    if not to_numbers:
        return False

    whatsapp_thread = threading.Thread(target=_send_via_whatsapp, args=(message_body, to_numbers))
    whatsapp_thread.daemon = True
    whatsapp_thread.start()
    return True