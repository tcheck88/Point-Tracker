"""
alerts.py - Leer México Alert System
Updated: Increased Timeout to 60s + Googlemail Alias to bypass routing blocks.
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
from db_utils import get_db_connection 

logger = logging.getLogger(__name__)

# Config
COOLDOWN_SECONDS = 5 # Keep low for testing
_last_alert_time = 0 

def _log_to_db(action_type, details):
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

def send_alert(subject, message, error_obj=None, to_emails=None, attachment_name=None, attachment_data=None):
    global _last_alert_time
    
    if not attachment_name:
        if (time.time() - _last_alert_time) < COOLDOWN_SECONDS:
            return False

    # CONFIG: Use googlemail.com alias if server var is default
    env_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    if env_server == 'smtp.gmail.com':
        smtp_server = 'smtp.googlemail.com'
    else:
        smtp_server = env_server

    smtp_port = int(os.getenv('MAIL_PORT', 465)) # Default to 465 now
    sender_email = os.getenv('MAIL_USERNAME')
    sender_password = os.getenv('MAIL_PASSWORD')
    
    recipients = []
    if to_emails: recipients = [e.strip() for e in to_emails if e.strip()]
    if not recipients:
        default = os.getenv('ADMIN_EMAIL')
        if default: recipients = [default]

    if not sender_email or not recipients:
        _log_to_db("EMAIL_CONFIG_ERROR", "Missing Config")
        return False

    try:
        # 3. RESOLVE
        addr_info = socket.getaddrinfo(smtp_server, smtp_port, socket.AF_INET)
        ipv4 = addr_info[0][4][0]

        _log_to_db("DEBUG_CONNECT", f"Server: {smtp_server} | IP: {ipv4} | Port: {smtp_port}")

        # 4. CONNECT (Increased Timeout)
        server = None
        if smtp_port == 465:
            # SSL Strategy
            server = smtplib.SMTP_SSL(ipv4, smtp_port, timeout=60)
        else:
            # TLS Strategy
            server = smtplib.SMTP(ipv4, smtp_port, timeout=60)
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
                msg.attach(MIMEText(message, 'html'))

                if attachment_name and attachment_data:
                    part = MIMEApplication(attachment_data, Name=attachment_name)
                    part['Content-Disposition'] = f'attachment; filename="{attachment_name}"'
                    msg.attach(part)

                server.send_message(msg)
        
        if not attachment_name: _last_alert_time = time.time()
        
        _log_to_db("EMAIL_SENT", f"Subject: {subject} | To: {recipients}")
        return True

    except Exception as e:
        _log_to_db("EMAIL_FAILED", f"SMTP Error: {str(e)}")
        return False