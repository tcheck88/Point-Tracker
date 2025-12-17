import smtplib
import os
import logging
import traceback
import time  # <--- Added for tracking time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# Minimum seconds between emails to prevent spamming
# 600 seconds = 10 minutes
COOLDOWN_SECONDS = 600 

# Track the last time an email was successfully sent
# We use a global variable to persist state while the app is running
_last_alert_time = 0 

def send_alert(subject, message, error_obj=None):
    """
    Sends an HTML email alert via SMTP with rate limiting.
    """
    global _last_alert_time
    
    # 1. CHECK COOLDOWN
    # Calculate how much time passed since the last email
    current_time = time.time()
    time_since_last = current_time - _last_alert_time
    
    if time_since_last < COOLDOWN_SECONDS:
        # If it's too soon, skip sending the email but log it locally
        logger.warning(f"EMAIL SUPPRESSED: Alert '{subject}' blocked by cooldown ({int(COOLDOWN_SECONDS - time_since_last)}s remaining).")
        return False

# 2. Retrieve Configuration
    smtp_server = os.getenv('MAIL_SERVER')
    smtp_port = os.getenv('MAIL_PORT')
    sender_email = os.getenv('MAIL_USERNAME')
    sender_password = os.getenv('MAIL_PASSWORD')
    recipient_email = os.getenv('ADMIN_EMAIL')

    # Add the safety check here
    try:
        port = int(smtp_port) if smtp_port else 587
    except (ValueError, TypeError):
        port = 587 # Default to TLS port

    if not all([smtp_server, sender_email, sender_password, recipient_email]):
        # Change logger.error to print to avoid the infinite crash loop
        print("ALERT SYSTEM DISABLED: Missing email environment variables.")
        return False
    
    
    try:
        # 3. Build HTML Content
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #d9534f;">⚠️ System Alert: {subject}</h2>
                <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Message:</strong><br>{message}</p>
        """

        if error_obj:
            tb_str = "".join(traceback.format_exception(type(error_obj), error_obj, error_obj.__traceback__))
            html_content += f"""
                <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                <h3 style="color: #555;">Technical Details (Traceback)</h3>
                <div style="background-color: #f8f9fa; border: 1px solid #ddd; padding: 15px; border-radius: 5px; overflow-x: auto;">
                    <pre style="margin: 0; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; color: #c7254e;">{tb_str}</pre>
                </div>
            """

        html_content += """
                <hr>
                <p style="font-size: 12px; color: #777;">This is an automated message from the Leer México Point Tracker.</p>
            </body>
        </html>
        """


        # 4. Send Email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"[Leer México] {subject}"
        msg.attach(MIMEText(html_content, 'html'))

        # Use SMTP_SSL for port 465, or standard SMTP + starttls for 587
        try:
            if port == 465:
                server = smtplib.SMTP_SSL(smtp_server, port, timeout=10)
            else:
                server = smtplib.SMTP(smtp_server, port, timeout=10)
                server.starttls()  # Upgrade to secure connection
            
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
            
            _last_alert_time = current_time
            return True
        except Exception as e:
            print(f"SMTP Error: {e}") # Avoid logger.error here too
            return False


        # 5. UPDATE TIMESTAMP
        # Only update this if the email actually sent successfully
        _last_alert_time = current_time
        
        logger.info(f"Alert email sent to {recipient_email}: {subject}")
        return True

    except Exception as e:
        logger.critical(f"FAILED TO SEND EMAIL ALERT. Error: {e}")
        return False

# Quick Test Block
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing Rate Limiting...")
    
    # 1. Send First Alert (Should Succeed)
    print("Attempting Alert 1...")
    send_alert("Test 1", "This is the first test.")
    
    # 2. Send Second Alert immediately (Should be Blocked)
    print("\nAttempting Alert 2 (Immediate)...")
    success = send_alert("Test 2", "This should be blocked.")
    
    if not success:
        print(" Alert 2 was correctly blocked by rate limiting.")
    else:
        print("Alert 2 was sent! Rate limiting failed.")