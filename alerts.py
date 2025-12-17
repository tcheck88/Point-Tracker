"""
alerts.py - Leer México Alert System
Includes: IPv4 forcing for Render, Rate Limiting (Cooldown), and Full Logging.
"""

import smtplib
import os
import logging
import socket
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# Minimum seconds between emails to prevent spamming (10 minutes)
COOLDOWN_SECONDS = 600 

# Global variable to persist state while the app is running
_last_alert_time = 0 

def send_alert(subject, message, error_obj=None):
    """
    Sends an HTML email alert via SMTP with IPv4 forcing and rate limiting.
    """
    global _last_alert_time
    
    # 1. RATE LIMITING (COOLDOWN)
    current_time = time.time()
    time_since_last = current_time - _last_alert_time
    
    if time_since_last < COOLDOWN_SECONDS:
        logger.warning(f"EMAIL SUPPRESSED: Alert '{subject}' blocked by cooldown. Remaining: {int(COOLDOWN_SECONDS - time_since_last)}s")
        return False

    # 2. CONFIGURATION & VALIDATION
    smtp_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('MAIL_PORT', 587))
    sender_email = os.getenv('MAIL_USERNAME')
    sender_password = os.getenv('MAIL_PASSWORD')
    recipient_email = os.getenv('ADMIN_EMAIL')

    if not all([sender_email, sender_password, recipient_email]):
        logger.error("ALERT SYSTEM DISABLED: Missing MAIL_USERNAME, MAIL_PASSWORD, or ADMIN_EMAIL.")
        return False

    try:
        # 3. FORCE IPv4 RESOLUTION (Critical for Render)
        # Bypasses [Errno 101] Network is unreachable
        addr_info = socket.getaddrinfo(smtp_server, smtp_port, socket.AF_INET)
        ipv4_address = addr_info[0][4][0]
        logger.info(f"Resolved {smtp_server} to {ipv4_address}")

        # 4. BUILD EMAIL CONTENT
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"[Leer México] {subject}"

        html_body = f"""
        <html>
            <body style="font-family: sans-serif; color: #333;">
                <h2 style="color: #d9534f;">⚠️ System Alert: {subject}</h2>
                <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Message:</strong> {message}</p>
        """
        
        if error_obj:
            html_body += f"<p><strong>Technical Error:</strong> {str(error_obj)}</p>"
            
        html_body += "</body></html>"
        msg.attach(MIMEText(html_body, 'html'))

        # 5. SEND VIA SMTP
        # Timeout ensures the web server doesn't hang forever
        with smtplib.SMTP(ipv4_address, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        # 6. UPDATE STATE ON SUCCESS
        _last_alert_time = current_time
        logger.info(f"Alert successfully sent to {recipient_email}")
        return True

    except socket.timeout:
        logger.error("SMTP Error: Connection timed out.")
        return False
    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")
        return False