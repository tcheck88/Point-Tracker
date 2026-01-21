"""
alerts.py - Leer México Alert System
Fixed: Prevents 'Death Loop' by using print() for internal errors instead of logger.
Updated: Supports dynamic recipient lists from database.
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

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# Minimum seconds between emails to prevent spamming (10 minutes)
COOLDOWN_SECONDS = 600 

# Global variable to persist state while the app is running
_last_alert_time = 0 

# Update signature to accept optional to_emails list

def send_alert(subject, message, error_obj=None, to_emails=None, attachment_name=None, attachment_data=None):
    """
    Sends an email alert. Supports 'attachment_name' (str) and 'attachment_data' (bytes).
    """
    global _last_alert_time
    
    # 1. COOLDOWN CHECK
    # We skip the cooldown check if this is a Report (indicated by having an attachment)
    if not attachment_name:
        current_time = time.time()
        time_since_last = current_time - _last_alert_time
        if time_since_last < COOLDOWN_SECONDS:
            return False

    # 2. CONFIGURATION
    smtp_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('MAIL_PORT', 587))
    sender_email = os.getenv('MAIL_USERNAME')
    sender_password = os.getenv('MAIL_PASSWORD')
    
    # Determine Recipients
    recipients = []
    if to_emails and isinstance(to_emails, list):
        recipients = [e.strip() for e in to_emails if e.strip()]
    
    if not recipients:
        default_admin = os.getenv('ADMIN_EMAIL')
        if default_admin:
            recipients = [default_admin]

    if not sender_email or not sender_password or not recipients:
        print(f"[{datetime.now()}] ALERT ABORTED: Missing config or recipients.")
        return False

    try:
        # 3. FORCE IPv4 (Render Fix)
        addr_info = socket.getaddrinfo(smtp_server, smtp_port, socket.AF_INET)
        ipv4_address = addr_info[0][4][0]

        with smtplib.SMTP(ipv4_address, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            
            for recipient in recipients:
                # Environment Tagging logic
                is_test = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
                env_tag = "[TEST SYSTEM]" if is_test else "[PROD]"
                header_color = "#f0ad4e" if is_test else "#d9534f"

                msg = MIMEMultipart()
                msg['From'] = sender_email
                msg['To'] = recipient
                msg['Subject'] = f"{env_tag} {subject}"

                html_body = f"""
                <html><body style="font-family: sans-serif; color: #333;">
                    <h2 style="color: {header_color};">{subject}</h2>
                    <p>{message}</p>
                    <p><small>Sent: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></p>
                </body></html>
                """
                msg.attach(MIMEText(html_body, 'html'))

                # --- NEW: ATTACHMENT LOGIC ---
                if attachment_name and attachment_data:
                    part = MIMEApplication(attachment_data, Name=attachment_name)
                    part['Content-Disposition'] = f'attachment; filename="{attachment_name}"'
                    msg.attach(part)
                # -----------------------------

                server.send_message(msg)
        
        # Only update the cooldown timer if this wasn't a report
        if not attachment_name:
            _last_alert_time = time.time()
            
        logger.info(f"Email sent to {recipients}")
        return True

    except Exception as e:
        print(f"[{datetime.now()}] Failed to send email: {e}")
        return False

