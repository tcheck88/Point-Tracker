"""
alerts.py - Leer México Alert System
Updated: Universal Port Support (465/587) + Internal Audit Logging
"""
import smtplib
import os
import logging
import socket
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# --- NEW: Import DB Connection for direct logging ---
from db_utils import get_db_connection 

logger = logging.getLogger(__name__)

# Config
COOLDOWN_SECONDS = 600
_last_alert_time = 0 

def _log_to_db(action_type, details):
    """
    Helper to write directly to audit_log without circular imports.
    """
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
        # Fallback to console if DB fails
        print(f"[{datetime.now()}] Failed to write to audit log: {e}")

def send_alert(subject, message, error_obj=None, to_emails=None, attachment_name=None, attachment_data=None):
    global _last_alert_time
    
    # 1. COOLDOWN CHECK (Skip if Report)
    if not attachment_name:
        if (time.time() - _last_alert_time) < COOLDOWN_SECONDS:
            return False

    # 2. CONFIG
    smtp_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('MAIL_PORT', 587))
    sender_email = os.getenv('MAIL_USERNAME')
    sender_password = os.getenv('MAIL_PASSWORD')
    
    recipients = []
    if to_emails: recipients = [e.strip() for e in to_emails if e.strip()]
    if not recipients:
        default = os.getenv('ADMIN_EMAIL')
        if default: recipients = [default]

    if not sender_email or not recipients:
        _log_to_db("EMAIL_CONFIG_ERROR", "Missing MAIL_USERNAME, PASSWORD, or Recipients.")
        print(f"[{datetime.now()}] ALERT ABORTED: Missing config.")
        return False

    try:
        # 3. CONNECTION & SEND
        addr_info = socket.getaddrinfo(smtp_server, smtp_port, socket.AF_INET)
        ipv4 = addr_info[0][4][0]

        # Port Detection Logic
        server = None
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(ipv4, smtp_port, timeout=20)
        else:
            server = smtplib.SMTP(ipv4, smtp_port, timeout=20)
            server.starttls()

        with server:
            server.login(sender_email, sender_password)
            
            for recipient in recipients:
                is_test = os.getenv('FLASK_DEBUG', '0') == '1'
                tag = "[TEST SYSTEM]" if is_test else "[PROD]"
                
                msg = MIMEMultipart()
                msg['From'] = sender_email
                msg['To'] = recipient
                msg['Subject'] = f"{tag} {subject}"

                msg.attach(MIMEText(message, 'html')) # Message is already HTML string

                if attachment_name and attachment_data:
                    part = MIMEApplication(attachment_data, Name=attachment_name)
                    part['Content-Disposition'] = f'attachment; filename="{attachment_name}"'
                    msg.attach(part)

                server.send_message(msg)
        
        if not attachment_name: _last_alert_time = time.time()
        
        # --- SUCCESS LOG ---
        _log_to_db("EMAIL_SENT", f"Subject: {subject} | To: {recipients}")
        logger.info(f"Email sent to {recipients}")
        return True

    except Exception as e:
        # --- FAILURE LOG (Capture the specific error) ---
        error_msg = str(e)
        print(f"[{datetime.now()}] EMAIL FAILED: {error_msg}")
        _log_to_db("EMAIL_FAILED", f"SMTP Error: {error_msg}")
        return False