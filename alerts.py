"""
alerts.py - Leer México Alert System
Updated: SENDGRID API VERSION (HTTP)
Replaces SMTP with SendGrid Web API for 100% reliability on Cloud Hosting.
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

def _send_via_sendgrid(subject, message, to_emails, attachment_name, attachment_data):
    """
    Sends email via SendGrid Web API (HTTP).
    Never times out, never gets blocked by SMTP firewalls.
    """
    api_key = os.getenv('SENDGRID_API_KEY')
    sender_email = os.getenv('MAIL_USERNAME') # Must be the verified sender in SendGrid
    
    if not api_key:
        _log_to_db("EMAIL_CONFIG_ERROR", "Missing SENDGRID_API_KEY")
        return

    # 1. Prepare Recipients
    # SendGrid API expects a list of objects: [{"email": "a@b.com"}, ...]
    personalizations = [{"to": [{"email": email}]} for email in to_emails]
    
    # 2. Prepare Attachment (if any)
    attachments_json = []
    if attachment_name and attachment_data:
        # SendGrid expects base64 encoded string
        encoded_data = base64.b64encode(attachment_data).decode('utf-8')
        attachments_json.append({
            "content": encoded_data,
            "filename": attachment_name,
            "type": "text/csv", # Defaulting to CSV for reports
            "disposition": "attachment"
        })

    # 3. Build Payload
    payload = {
        "personalizations": personalizations,
        "from": {"email": sender_email},
        "subject": subject,
        "content": [{"type": "text/html", "value": message}]
    }
    
    if attachments_json:
        payload["attachments"] = attachments_json

    try:
        # 4. Send Request (HTTP)
        conn = http.client.HTTPSConnection("api.sendgrid.com")
        headers = {
            'Authorization': f"Bearer {api_key}",
            'Content-Type': 'application/json'
        }
        
        json_payload = json.dumps(payload)
        conn.request("POST", "/v3/mail/send", json_payload, headers)
        
        res = conn.getresponse()
        data = res.read()
        
        # 5. Check Result
        # SendGrid returns 202 Accepted for success
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
    
    # Cooldown Check
    if not attachment_name:
        if (time.time() - _last_alert_time) < COOLDOWN_SECONDS:
            return False
        _last_alert_time = time.time()
        
    # Determine Recipients
    recipients = []
    if to_emails: recipients = [e.strip() for e in to_emails if e.strip()]
    if not recipients:
        default = os.getenv('ADMIN_EMAIL')
        if default: recipients = [default]
        
    if not recipients:
        _log_to_db("EMAIL_CONFIG_ERROR", "No recipients found.")
        return False

    # --- THREADED EXECUTION ---
    email_thread = threading.Thread(
        target=_send_via_sendgrid,
        args=(subject, message, recipients, attachment_name, attachment_data)
    )
    email_thread.daemon = True
    email_thread.start()
    
    return True