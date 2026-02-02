"""
alerts.py - Leer México Alert System
Updated: SENDGRID API + TWILIO SMS (Configurable)
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
from twilio.rest import Client as TwilioClient  # <--- NEW IMPORT

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

# --- NEW: SMS HELPER FUNCTIONS ---
def _check_sms_enabled():
    """Returns True if SMS is enabled in system_settings, else False."""
    try:
        conn = get_db_connection()
        if not conn: return False
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'ENABLE_SMS_FOR_ADMIN_MESSAGES'")
        row = cur.fetchone()
        conn.close()
        
        if row:
            val = row['setting_value'] if isinstance(row, dict) else row[0]
            # Check for various "truthy" string values
            return str(val).lower() in ('true', '1', 'yes', 'on')
        return False
    except Exception as e:
        logger.error(f"Error checking SMS config: {e}")
        return False

def _send_via_twilio(body, to_numbers):
    # 1. Credentials Check
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_PHONE_NUMBER')

    if not all([account_sid, auth_token, from_number]):
        _log_to_db("SMS_SKIPPED", "Missing Twilio credentials in .env")
        return

    try:
        client = TwilioClient(account_sid, auth_token)
        
        for number in to_numbers:
            clean_number = number.strip()
            if not clean_number: continue
            
            try:
                message = client.messages.create(
                    body=body,
                    from_=from_number,
                    to=clean_number
                )
                _log_to_db("SMS_SENT", f"SID: {message.sid} To: {clean_number}")
                
            except Exception as inner_e:
                # Catch specific Twilio errors (like 'Trial Account' or 'Unverified Number')
                # Log it, but DO NOT CRASH. Continue to the next number.
                logger.error(f"Failed to send to {clean_number}: {inner_e}")
                _log_to_db("SMS_FAILED_INDIVIDUAL", f"To: {clean_number} Error: {str(inner_e)}")
            
    except Exception as e:
        # Catch connection errors (e.g., Twilio API down)
        logger.error(f"Twilio Client Error: {e}")
        _log_to_db("SMS_FAILED_GLOBAL", str(e))

def send_sms(message_body, to_numbers=None):
    """
    Public function. Checks configuration before sending.
    """
    # 1. Check the Master Switch
    if not _check_sms_enabled():
        return False

    if not to_numbers:
        _log_to_db("SMS_ERROR", "No recipient numbers provided.")
        return False

    # 2. Spawn Thread
    sms_thread = threading.Thread(
        target=_send_via_twilio,
        args=(message_body, to_numbers)
    )
    sms_thread.daemon = True
    sms_thread.start()
    return True
# ---------------------------------

def _send_via_sendgrid(subject, message, to_emails, attachment_name, attachment_data):
    """
    Sends email via SendGrid Web API (HTTP).
    """
    api_key = os.getenv('SENDGRID_API_KEY')
    sender_email = os.getenv('MAIL_USERNAME') 
    
    if not api_key:
        _log_to_db("EMAIL_CONFIG_ERROR", "Missing SENDGRID_API_KEY")
        return

    personalizations = [{"to": [{"email": email}]} for email in to_emails]
    
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
        "content": [{"type": "text/html", "value": message}]
    }
    
    if attachments_json:
        payload["attachments"] = attachments_json

    try:
        conn = http.client.HTTPSConnection("api.sendgrid.com")
        headers = {
            'Authorization': f"Bearer {api_key}",
            'Content-Type': 'application/json'
        }
        
        json_payload = json.dumps(payload)
        conn.request("POST", "/v3/mail/send", json_payload, headers)
        
        res = conn.getresponse()
        data = res.read()
        
        if res.status in [200, 201, 202]:
            _log_to_db("EMAIL_SENT", f"Via SendGrid API. To: {to_emails}")
        else:
            error_msg = f"Status: {res.status} | Body: {data.decode('utf-8')}"
            _log_to_db("EMAIL_FAILED", error_msg)
            print(f"SendGrid Error: {error_msg}")

    except Exception as e:
        _log_to_db("EMAIL_FAILED", f"API Error: {str(e)}")

def send_alert(subject, message, error_obj=None, to_emails=None, attachment_name=None, attachment_data=None):
    """
    Main entry point. Spawns thread and returns immediately.
    """
    global _last_alert_time
    
    if not attachment_name:
        if (time.time() - _last_alert_time) < COOLDOWN_SECONDS:
            return False
        _last_alert_time = time.time()
        
    recipients = []
    if to_emails: recipients = [e.strip() for e in to_emails if e.strip()]
    if not recipients:
        default = os.getenv('ADMIN_EMAIL')
        if default: recipients = [default]
        
    if not recipients:
        _log_to_db("EMAIL_CONFIG_ERROR", "No recipients found.")
        return False

    email_thread = threading.Thread(
        target=_send_via_sendgrid,
        args=(subject, message, recipients, attachment_name, attachment_data)
    )
    email_thread.daemon = True
    email_thread.start()
    
    return True