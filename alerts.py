"""
alerts.py - Leer México Alert System
Updated: Switched from SendGrid to Resend for Email/SMS Gateway
Supports Resend, Twilio SMS, and WhatsApp Automation
"""
import os
import json
import logging
import threading
import subprocess
import time
import base64
import resend  # Updated: Using Resend SDK
from datetime import datetime
from db_utils import get_db_connection
from twilio.rest import Client as TwilioClient

logger = logging.getLogger(__name__)

# Config
COOLDOWN_SECONDS = 5
_last_alert_time = 0

# Path to WhatsApp service scripts
WHATSAPP_SERVICE_DIR = os.path.join(os.path.dirname(__file__), 'whatsapp_service')

# Initialize Resend
resend.api_key = os.getenv('RESEND_API_KEY')

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
    """Returns True if WhatsApp automation is enabled."""
    try:
        conn = get_db_connection()
        if not conn: return False
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'ENABLE_WHATSAPP_AUTOMATION'")
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

def _send_via_resend(subject, message, to_emails, attachment_name, attachment_data, log_label="EMAIL"):
    """Updated: Uses Resend API instead of SendGrid."""
    api_key = os.getenv('RESEND_API_KEY')
    sender_email = os.getenv('MAIL_USERNAME') 
    
    if not api_key:
        _log_to_db(f"{log_label}_CONFIG_ERROR", "Missing RESEND_API_KEY")
        return

    # Prep Attachments for Resend SDK
    resend_attachments = []
    if attachment_name and attachment_data:
        # Resend accepts base64 strings or bytes for content
        encoded_data = base64.b64encode(attachment_data).decode('utf-8')
        resend_attachments.append({
            "content": encoded_data,
            "filename": attachment_name
        })

    try:
        # Determine content type (Text for SMS Gateway, HTML for standard Email)
        email_params = {
            "from": sender_email,
            "to": to_emails,
            "subject": subject,
            "attachments": resend_attachments
        }

        if log_label == "SMS_GATEWAY":
            email_params["text"] = message
        else:
            email_params["html"] = message

        # Trigger Send
        response = resend.Emails.send(email_params)
        
        if response and 'id' in response:
            _log_to_db(f"{log_label}_SENT", f"ID: {response['id']} To: {to_emails}")
        else:
            _log_to_db(f"{log_label}_FAILED", f"Unexpected response format: {response}")

    except Exception as e:
        logger.error(f"Resend API Error: {e}")
        _log_to_db(f"{log_label}_FAILED", f"API Error: {str(e)}")

def _send_via_whatsapp(body, to_numbers):
    send_script = os.path.join(WHATSAPP_SERVICE_DIR, 'send_message.js')

    if not os.path.exists(send_script):
        _log_to_db("WHATSAPP_SKIPPED", "WhatsApp service not installed")
        logger.error(f"WhatsApp send script not found: {send_script}")
        return

    for number in to_numbers:
        clean_number = number.strip()
        if not clean_number: continue

        try:
            result = subprocess.run(
                ['node', send_script, clean_number, body],
                capture_output=True,
                text=True,
                timeout=90,
                cwd=WHATSAPP_SERVICE_DIR,
                env={**os.environ, 'DATABASE_URL': os.getenv('DATABASE_URL', '')}
            )

            if result.returncode == 0:
                _log_to_db("WHATSAPP_SENT", f"To: {clean_number}")
            elif result.returncode in (2, 3):
                _log_to_db("WHATSAPP_SESSION_ERROR", f"Exit code {result.returncode}: {result.stderr}")
                _send_whatsapp_session_alert(result.returncode)
                break 
            else:
                _log_to_db("WHATSAPP_FAILED", f"To: {clean_number} Exit: {result.returncode} Err: {result.stderr}")

        except subprocess.TimeoutExpired:
            _log_to_db("WHATSAPP_TIMEOUT", f"To: {clean_number}")
        except Exception as e:
            _log_to_db("WHATSAPP_ERROR", f"To: {clean_number} Error: {str(e)}")


def _send_whatsapp_session_alert(exit_code):
    """Send email alert via Resend when WhatsApp session needs attention."""
    try:
        admin_email = os.getenv('ADMIN_EMAIL')
        if not admin_email:
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'ALERT_RECIPIENT_EMAILS'")
                row = cur.fetchone()
                conn.close()
                if row:
                    val = row['setting_value'] if isinstance(row, dict) else row[0]
                    if val:
                        admin_email = val.split(',')[0].strip()

        if not admin_email: return

        if exit_code == 2:
            subject = "WhatsApp Setup Required - Point Tracker"
            message = "<h2>WhatsApp Session Not Found</h2><p>Please scan the QR code in the admin panel.</p>"
        else:
            subject = "WhatsApp Re-Link Required - Point Tracker"
            message = "<h2>WhatsApp Session Expired</h2><p>Please visit the admin panel and scan a new QR code.</p>"

        _send_via_resend(subject, message, [admin_email], None, None, "WHATSAPP_ALERT")

    except Exception as e:
        logger.error(f"Failed to send WhatsApp session alert: {e}")

# --- PUBLIC FUNCTIONS ---

def send_sms(message_body, to_numbers=None):
    if not _check_sms_enabled(): return False
    if not to_numbers: return False
    threading.Thread(target=_send_via_twilio, args=(message_body, to_numbers), daemon=True).start()
    return True

def send_email_sms(message_body, recipient_gateways=None):
    if not _check_email_sms_enabled(): return False
    if not recipient_gateways: return False
    
    threading.Thread(
        target=_send_via_resend, # Updated: Now points to Resend
        args=("Alert", message_body, recipient_gateways, None, None, "SMS_GATEWAY"),
        daemon=True
    ).start()
    return True

def send_alert(subject, message, error_obj=None, to_emails=None, attachment_name=None, attachment_data=None):
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

    threading.Thread(
        target=_send_via_resend, # Updated: Now points to Resend
        args=(subject, message, recipients, attachment_name, attachment_data, "EMAIL"),
        daemon=True
    ).start()
    return True

def send_whatsapp(message_body, to_numbers=None):
    if not _check_whatsapp_enabled(): return False
    if not to_numbers: return False
    threading.Thread(target=_send_via_whatsapp, args=(message_body, to_numbers), daemon=True).start()
    return True

def check_whatsapp_session():
    check_script = os.path.join(WHATSAPP_SERVICE_DIR, 'check_session.js')
    if not os.path.exists(check_script): return {'status': 'not_installed'}
    try:
        result = subprocess.run(['node', check_script], capture_output=True, text=True, timeout=45, cwd=WHATSAPP_SERVICE_DIR, env={**os.environ, 'DATABASE_URL': os.getenv('DATABASE_URL', '')})
        return json.loads(result.stdout.strip()) if result.stdout.strip() else {'status': 'error', 'message': result.stderr}
    except Exception as e: return {'status': 'error', 'message': str(e)}
