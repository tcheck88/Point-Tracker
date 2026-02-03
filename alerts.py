"""
alerts.py - Leer México Alert System
Updated: Supports SendGrid, Twilio SMS, Email-to-SMS (Gateway), AND WhatsApp Automation
"""
import os
import json
import logging
import threading
import subprocess
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

# Path to WhatsApp service scripts
WHATSAPP_SERVICE_DIR = os.path.join(os.path.dirname(__file__), 'whatsapp_service')

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
    Send WhatsApp messages using whatsapp-web.js via Node subprocess.
    Session is persisted in Supabase for restart resilience.

    Exit codes from send_message.js:
      0 = Success
      2 = No session (need QR scan)
      3 = Session expired (need QR re-scan)
      4 = Send failed
      5 = Connection timeout
    """
    send_script = os.path.join(WHATSAPP_SERVICE_DIR, 'send_message.js')

    if not os.path.exists(send_script):
        _log_to_db("WHATSAPP_SKIPPED", "WhatsApp service not installed")
        logger.error(f"WhatsApp send script not found: {send_script}")
        return

    for number in to_numbers:
        clean_number = number.strip()
        if not clean_number:
            continue

        try:
            # Call Node.js script to send message
            result = subprocess.run(
                ['node', send_script, clean_number, body],
                capture_output=True,
                text=True,
                timeout=90,  # 90 second timeout
                cwd=WHATSAPP_SERVICE_DIR,
                env={**os.environ, 'DATABASE_URL': os.getenv('DATABASE_URL', '')}
            )

            if result.returncode == 0:
                _log_to_db("WHATSAPP_SENT", f"To: {clean_number}")
                logger.info(f"WhatsApp sent to {clean_number}")
            elif result.returncode in (2, 3):
                # Session issue - send alert email to admin
                _log_to_db("WHATSAPP_SESSION_ERROR", f"Exit code {result.returncode}: {result.stderr}")
                logger.error(f"WhatsApp session error: {result.stderr}")
                _send_whatsapp_session_alert(result.returncode)
                break  # Don't try other numbers if session is broken
            else:
                _log_to_db("WHATSAPP_FAILED", f"To: {clean_number} Exit: {result.returncode} Err: {result.stderr}")
                logger.error(f"WhatsApp failed for {clean_number}: {result.stderr}")

        except subprocess.TimeoutExpired:
            _log_to_db("WHATSAPP_TIMEOUT", f"To: {clean_number}")
            logger.error(f"WhatsApp send timeout for {clean_number}")
        except Exception as e:
            _log_to_db("WHATSAPP_ERROR", f"To: {clean_number} Error: {str(e)}")
            logger.error(f"WhatsApp error for {clean_number}: {e}")


def _send_whatsapp_session_alert(exit_code):
    """Send email alert when WhatsApp session needs attention."""
    try:
        # Get admin email
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

        if not admin_email:
            logger.error("No admin email configured for WhatsApp session alert")
            return

        if exit_code == 2:
            subject = "WhatsApp Setup Required - Point Tracker"
            message = """
            <h2>WhatsApp Session Not Found</h2>
            <p>The Point Tracker WhatsApp automation has no active session.</p>
            <p><strong>Action Required:</strong> Please visit the admin panel and scan the QR code to link WhatsApp.</p>
            <ol>
                <li>Go to <code>/admin/whatsapp-setup</code></li>
                <li>Scan the QR code with the WhatsApp app on your phone</li>
                <li>Wait for confirmation</li>
            </ol>
            <p>WhatsApp alerts are paused until this is completed.</p>
            """
        else:  # exit_code == 3
            subject = "WhatsApp Re-Link Required - Point Tracker"
            message = """
            <h2>WhatsApp Session Expired</h2>
            <p>The Point Tracker WhatsApp session has expired and needs to be re-linked.</p>
            <p><strong>Action Required:</strong> Please visit the admin panel and scan a new QR code.</p>
            <ol>
                <li>Go to <code>/admin/whatsapp-setup</code></li>
                <li>Scan the QR code with the WhatsApp app on your phone</li>
                <li>Wait for confirmation</li>
            </ol>
            <p>WhatsApp alerts are paused until this is completed.</p>
            """

        # Send via SendGrid (don't use send_alert to avoid cooldown issues)
        _send_via_sendgrid(subject, message, [admin_email], None, None, "WHATSAPP_ALERT")

    except Exception as e:
        logger.error(f"Failed to send WhatsApp session alert: {e}")

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
    WhatsApp Trigger via whatsapp-web.js automation.

    Phone numbers should be in E.164 format (e.g., '+15551234567').
    Session is persisted in Supabase and auto-restored on restart.

    If session is expired or missing, an email alert is sent to admin
    with instructions to re-scan the QR code.

    Requires:
    - ENABLE_WHATSAPP_AUTOMATION = 'true' in system_settings
    - WHATSAPP_RECIPIENT_NUMBERS configured in system_settings
    - Node.js installed and whatsapp_service dependencies installed
    """
    if not _check_whatsapp_enabled():
        return False
    if not to_numbers:
        return False

    whatsapp_thread = threading.Thread(target=_send_via_whatsapp, args=(message_body, to_numbers))
    whatsapp_thread.daemon = True
    whatsapp_thread.start()
    return True


def check_whatsapp_session():
    """
    Check WhatsApp session status. Called on startup or from admin panel.
    Returns dict with status info.
    """
    check_script = os.path.join(WHATSAPP_SERVICE_DIR, 'check_session.js')

    if not os.path.exists(check_script):
        return {'status': 'not_installed', 'message': 'WhatsApp service not installed'}

    try:
        result = subprocess.run(
            ['node', check_script],
            capture_output=True,
            text=True,
            timeout=45,
            cwd=WHATSAPP_SERVICE_DIR,
            env={**os.environ, 'DATABASE_URL': os.getenv('DATABASE_URL', '')}
        )

        # Parse JSON output from stdout
        if result.stdout.strip():
            return json.loads(result.stdout.strip())
        else:
            return {'status': 'error', 'message': result.stderr}

    except subprocess.TimeoutExpired:
        return {'status': 'timeout', 'message': 'Session check timed out'}
    except json.JSONDecodeError as e:
        return {'status': 'error', 'message': f'Invalid response: {e}'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}