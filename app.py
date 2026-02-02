"""
app.py - Leer México Activity Manager backend (PostgreSQL Version)
Restored Production Version
"""

from dotenv import load_dotenv  
import os
import sys
import io
import csv
import logging
import datetime
import traceback
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify, abort, send_file, redirect, url_for, render_template, send_from_directory, session
from flask_babel import Babel 
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
from functools import wraps
import requests 


# --- IMPORTS FOR POSTGRESQL (LAZY LOAD PATTERN) ---
# We use this proxy technique to prevent "Cold Start" timeouts.
# Heavy modules are only imported when a function actually uses them.

import importlib
import threading  

class LazyModule:
    def __init__(self, module_name):
        self.module_name = module_name
        self._module = None
    
    def __getattr__(self, item):
        if self._module is None:
            self._module = importlib.import_module(self.module_name)
        return getattr(self._module, item)

# Define proxies for heavy modules
add_student = LazyModule('add_student')
student_search = LazyModule('student_search')
transaction_manager = LazyModule('transaction_manager')
alerts = LazyModule('alerts')

# Define wrappers for function imports
def get_db_connection():
    from db_utils import get_db_connection as _real
    return _real()

def init_db():
    from db_utils import init_db as _real
    return _real()
    

load_dotenv()  

# ---- 1. Paths and App Setup ----
APP_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(APP_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, 'app.log')

# Determine base directory for frozen (EXE) vs development
if getattr(sys, 'frozen', False):
    basedir = sys._MEIPASS
else:
    basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-key-change-this")

# ---- 2. Babel Localization Setup ----

def get_locale():
    # 1. Check URL parameters (highest priority) and save to session
    if 'lang' in request.args:
        lang = request.args.get('lang')
        if lang in app.config['LANGUAGES']:
            session['lang'] = lang  # <--- NEW: Saves choice to session
            logger.info(f"Language set to {lang} via URL")
            print(f"DEBUG message: Language set to {lang} via URL")  # <--- DEBUG
            return lang
            
    # 2. Check Session (persistence)
    if 'lang' in session:           # <--- NEW: Remembers choice on next page load
        logger.info(f"Language loaded from SESSION: {session['lang']}")
        return session['lang']
        
    # 3. Fallback to Browser Headers
    logger.info(f"DEBUG: Using default browser language")
    return request.accept_languages.best_match(app.config['LANGUAGES'].keys())


app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['BABEL_TRANSLATION_DIRECTORIES'] = os.path.join(basedir, 'translations') 
app.config['LANGUAGES'] = {'en': 'English', 'es': 'Español'}

babel = Babel(app, locale_selector=get_locale)

@app.context_processor
def inject_conf_var():
    return dict(get_locale=get_locale)

# ---- 3. Authentication Helper ----
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function
    
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow BOTH 'admin' and 'sysadmin' to access general admin tools
        if session.get('role') not in ['admin', 'sysadmin']:
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({"success": False, "message": "Access Denied: Admins only."}), 403
            else:
                return redirect(url_for('index')) 
        return f(*args, **kwargs)
    return decorated_function    

    

# ---- 4. Logging Setup ----

class EmailAlertHandler(logging.Handler):
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            try:
                # self.format(record) includes the traceback if logged via logger.exception()
                msg = self.format(record)
                
                # Define a wrapper function to send email without blocking
                def send_async():
                    try:
                        # Attempt to send the alert
                        alerts.send_alert(
                            subject=f"System Error: {record.levelname}", 
                            message=msg
                        )
                    except Exception as e:
                        logger.exception("Background Email Failed")
                        
                # Start the email task in a separate thread
                thread = threading.Thread(target=send_async)
                thread.start()

            except Exception:
                self.handleError(record)


file_handler = RotatingFileHandler(LOG_PATH, maxBytes=500000, backupCount=3)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

console_handler = StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# Clear existing handlers to prevent duplicates
for h in list(root_logger.handlers):
    root_logger.removeHandler(h)

root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)
root_logger.addHandler(EmailAlertHandler())

logger = logging.getLogger(__name__)



# --- HELPER: Enable Cron Job via API ---
def enable_wake_job():
    """
    Calls cron-job.org API to ENABLE the wake-up job.
    This ensures the service stays running after a real user logs in.
    """
    api_key = os.getenv('CRON_JOB_API_KEY')
    job_id = os.getenv('CRON_JOB_ID')
    
    if not api_key or not job_id:
        logger.warning("Cron Job API keys missing. Skipping auto-enable.")
        return

    url = f"https://api.cron-job.org/jobs/{job_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "job": {
            "enabled": True
        }
    }

    try:
        # We use PATCH to update specific fields (enabled: true)
        response = requests.patch(url, json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            logger.info(f"Successfully ENABLED Cron Job {job_id}")
        else:
            logger.error(f"Failed to enable Cron Job: {response.text}")
    except Exception as e:
        logger.error(f"Cron Job API Error: {e}")



@app.route('/api/maintenance/db-ping', methods=['GET'])
def maintain_db_connection():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return jsonify({"status": "success", "message": "Database pinged"}), 200
    except Exception as e:
        logger.error(f"DB Maintenance Ping Failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
   
    
# ---- 6. AUTOMATIC LOGGING MIDDLEWARE & SESSION TIMEOUT ----

@app.before_request
def before_request_logic():
    # 1. Start the timer for Request Logging
    request.start_time = datetime.datetime.utcnow()
    
    # 2. SECURITY FIX: Do NOT make session permanent.
    # This ensures the cookie is deleted when the browser closes.
    session.permanent = False 
    
    # 3. TIMEOUT CHECK (For users who leave the tab OPEN)
    if 'username' in session:
        now = datetime.datetime.now(datetime.timezone.utc)
        last_active = session.get('last_active')
        
        if last_active:
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=datetime.timezone.utc)
            
            # If the user left the tab open for > 60 mins, log it and kill it.
            if now - last_active > datetime.timedelta(minutes=60):
                try:
                    transaction_manager.log_audit_event(
                        action_type="SESSION_TIMEOUT",
                        details=f"User session expired (Idle Tab): {session.get('username')}",
                        recorded_by="system"
                    )
                except Exception:
                    logger.exception("Error logging session timeout")

                session.clear()
                return redirect(url_for('login', error="Session expired due to inactivity."))
        
        session['last_active'] = now
        
        
@app.after_request
def log_request(response):
    # Calculate how long the request took
    duration = datetime.datetime.utcnow() - request.start_time
    duration_ms = int(duration.total_seconds() * 1000)
    
    # Don't log static file requests (too noisy)
    if request.path.startswith('/static'):
        return response

    # Get user identity if logged in
    user = session.get('username', 'Guest')
    ip = request.remote_addr
    
    # Define log level based on status code
    if response.status_code >= 500:
        log_method = logger.error
    elif response.status_code >= 400:
        log_method = logger.warning
    else:
        log_method = logger.info

    # Log the event: [200] GET /students (User: admin) - 45ms
    log_method(
        f"[{response.status_code}] {request.method} {request.path} "
        f"(User: {user} | IP: {ip}) - {duration_ms}ms"
    )
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    # 1. Ignore standard HTTP errors (404, 405, etc.)
    # Let Flask handle these normally (e.g. show the default 404 page)
    if isinstance(e, HTTPException):
        return e

    # 2. Catch actual system crashes (Database fail, Code bugs)
    logger.exception(f"UNHANDLED SYSTEM ERROR: {str(e)}")
    return "Internal Server Error", 500


# ---- ROUTES START BELOW ----

# ---- Route used by cronjob to wake up and keep the service running.  This is a lighter weight function so it fits within the timeout limitations ------

@app.route('/api/cron/wake', methods=['GET'])
def cron_wake():
    return jsonify({"status": "awake"}), 200
    
    
    
@app.route('/api/cron/daily_report', methods=['GET'])
def cron_daily_report():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Fetch Students + Points Added AND Redeemed in Last 24 Hours
        # We join activity_log to sum positive points (Added) and negative points (Redeemed)
        cur.execute("""
            SELECT 
                s.full_name, 
                s.grade, 
                s.classroom, 
                s.total_points,
                COALESCE(SUM(CASE 
                    WHEN al.timestamp >= NOW() - INTERVAL '24 HOURS' AND al.points > 0 
                    THEN al.points 
                    ELSE 0 
                END), 0) as points_added_24h,
                COALESCE(SUM(CASE 
                    WHEN al.timestamp >= NOW() - INTERVAL '24 HOURS' AND al.points < 0 
                    THEN ABS(al.points) 
                    ELSE 0 
                END), 0) as points_redeemed_24h
            FROM students s
            LEFT JOIN activity_log al ON s.id = al.student_id
            WHERE s.active = TRUE 
            GROUP BY s.id
            ORDER BY s.grade ASC, s.classroom ASC, s.full_name ASC
        """)
        student_rows = cur.fetchall()

        # 2. Fetch Recipient List
        recipients = None
        cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'DAILY_POINT_LOG'")
        setting_row = cur.fetchone()
        if setting_row:
            val = setting_row['setting_value'] if isinstance(setting_row, dict) else setting_row[0]
            if val and val.strip():
                recipients = [e.strip() for e in val.split(',')]
        
        conn.close()

        # 3. Generate CSV (Now with 6 Columns)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Student Name', 'Grade', 'Classroom', 'Total Points', 'Points Added (Last 24h)', 'Points Redeemed (Last 24h)'])
        
        for row in student_rows:
            # Handle Dict/Tuple differences for robustness
            is_dict = isinstance(row, dict)
            r_name = row['full_name'] if is_dict else row[0]
            r_gr = row['grade'] if is_dict else row[1]
            r_cl = row['classroom'] if is_dict else row[2]
            r_pts = row['total_points'] if is_dict else row[3]
            r_added = row['points_added_24h'] if is_dict else row[4]
            r_redeemed = row['points_redeemed_24h'] if is_dict else row[5] # <--- NEW COLUMN
            
            writer.writerow([r_name, r_gr, r_cl, r_pts, r_added, r_redeemed])

        # 4. Send to the Group
        alerts.send_alert(
            subject="Daily Student Balance Report",
            message=f"Attached is the report for {datetime.datetime.now().strftime('%Y-%m-%d')}. It includes total balances, points earned, and points redeemed in the last 24 hours.",
            to_emails=recipients,
            attachment_name=f"Student_Balances_{datetime.datetime.now().strftime('%Y-%m-%d')}.csv",
            attachment_data=output.getvalue().encode('utf-8')
        )
        
        # 5. Log Audit Event
        transaction_manager.log_audit_event(
            action_type="DAILY_REPORT_RUN",
            details=f"Daily report sent to: {recipients or 'Default Admin'}",
            recorded_by="system_cron"
        )

        return jsonify({"success": True}), 200

    except Exception as e:
        logger.exception(f"Daily Student Point Log email Failed: {e}")
        try:
            transaction_manager.log_audit_event(
                action_type="DAILY_REPORT_FAILED",
                details=f"Error: {str(e)}",
                recorded_by="system_cron"
            )
        except:
            pass
        return jsonify({"error": str(e)}), 500
            


# --- Handle Language Switching ---
@app.route('/set_language', methods=['POST'])
def set_language():
    lang = request.form.get('language')
    if lang in app.config['LANGUAGES']:
        session['lang'] = lang
    # Redirect back to the page the user was on
    return redirect(request.referrer or url_for('index'))
# ---------------------------------------------



# 1. UPDATE THIS FUNCTION (Block inactive logins)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            return render_template('login.html', error="System Error: Database connection failed.")
            
        cur = conn.cursor()
        # Fetch 'active' status in addition to other fields
        cur.execute("SELECT username, password_hash, role, active FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        conn.close()

        if user:
            # Handle Dictionary vs Tuple cursor
            if isinstance(user, dict):
                stored_hash = user['password_hash']
                role = user['role']
                db_user = user['username']
                is_active = user['active']
            else:
                db_user = user[0]
                stored_hash = user[1]
                role = user[2]
                is_active = user[3] # Index 3 matches the SQL query order above

            # SECURITY CHECK: Block inactive users immediately
            if not is_active:
                 return render_template('login.html', error="Account is inactive. Please contact a System Administrator.")

            if check_password_hash(stored_hash, password):
                session['username'] = db_user
                session['role'] = role.strip() if role else 'staff'
                
                threading.Thread(target=enable_wake_job).start() 
                
                try:
                    transaction_manager.log_audit_event(
                        action_type="USER_LOGIN",
                        details=f"User logged in successfully: {db_user}",
                        recorded_by=db_user
                    )
                except Exception as e:
                    # Logs the message AND the full stack trace (File X, Line Y...)
                    logger.exception("Error logging login event")
                return redirect(url_for('index'))
        
        return render_template('login.html', error="Invalid credentials")
        
    return render_template('login.html')


# 2. UPDATE THIS FUNCTION (Fetch 'active' status for the list)
@app.route('/admin/users')
@login_required
def manage_users():
    current_role = session.get('role')
    
    if current_role not in ['sysadmin', 'admin']:
        return redirect(url_for('index'))

    msg = request.args.get('msg')
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Updated SQL to select 'active' column
    if current_role == 'sysadmin':
        cur.execute("SELECT id, username, role, active FROM users ORDER BY id ASC")
    else:
        cur.execute("SELECT id, username, role, active FROM users WHERE role != 'sysadmin' ORDER BY id ASC")
        
    users = cur.fetchall()
    conn.close()
    
    user_list = []
    for u in users:
        if isinstance(u, dict):
            user_list.append(u)
        else:
            # Update tuple mapping to include active at index 3
            user_list.append({'id': u[0], 'username': u[1], 'role': u[2], 'active': u[3]})

    return render_template('manage_users.html', users=user_list, msg=msg)


# 3. ADD THIS NEW FUNCTION (Handle the toggle)
@app.route('/admin/users/toggle_status', methods=['POST'])
@login_required
def toggle_user_status():
    current_role = session.get('role')
    staff_identity = session.get('username', 'system')
    
    if current_role not in ['sysadmin', 'admin']:
        return redirect(url_for('index'))

    user_id = request.form.get('user_id')
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # 1. Fetch Target to check permissions
        cur.execute("SELECT username, role, active FROM users WHERE id = %s", (user_id,))
        target = cur.fetchone()
        
        if not target:
            return redirect(url_for('manage_users', msg="Error: User not found."))

        target_name = target['username'] if isinstance(target, dict) else target[0]
        target_role = target['role'] if isinstance(target, dict) else target[1]
        current_status = target['active'] if isinstance(target, dict) else target[2]

        # 2. Prevent Admin from disabling SysAdmin
        if current_role != 'sysadmin' and target_role == 'sysadmin':
             return redirect(url_for('manage_users', msg="Access Denied: You cannot modify SysAdmin accounts."))

        # 3. Prevent Self-Lockout (Optional but smart)
        if target_name == staff_identity:
             return redirect(url_for('manage_users', msg="Error: You cannot deactivate your own account."))

        # 4. Toggle Status
        new_status = not current_status
        cur.execute("UPDATE users SET active = %s WHERE id = %s", (new_status, user_id))
        
        # 5. Log it
        status_str = "ACTIVATED" if new_status else "DEACTIVATED"
        transaction_manager.log_audit_event(
            action_type="USER_STATUS_CHANGE",
            details=f"{status_str} user account: {target_name}",
            recorded_by=staff_identity
        )
        
        conn.commit()
        return redirect(url_for('manage_users', msg=f"Success: User {target_name} is now {status_str}."))
        
    except Exception as e:
        conn.rollback()
        logger.exception(f"Toggle status failed: {e}")
        return redirect(url_for('manage_users', msg=f"Error: {str(e)}"))
    finally:
        conn.close()




@app.route('/logout')
def logout():
    user = session.get('username')
    # Check if this logout came from the auto-script
    is_timeout = request.args.get('timeout') == '1'

    if user:
        try:
            # Decide what to log
            if is_timeout:
                action = "SESSION_TIMEOUT"
                details = f"Session timed out (Auto-logout): {user}"
                recorder = "system"
            else:
                action = "USER_LOGOUT"
                details = f"User logged out manually: {user}"
                recorder = user

            transaction_manager.log_audit_event(
                action_type=action,
                details=details,
                recorded_by=recorder
            )
        except Exception as e:
            # Logs the message AND the full stack trace (File X, Line Y...)
            logger.exception("Error logging logout event")

    session.clear()
    
    # If it was a timeout, show a message on the login screen
    if is_timeout:
        return redirect(url_for('login', error="Session timed out due to inactivity."))
        
    return redirect(url_for('login'))
    

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/add_student')
@login_required
def add_student_page():
    return render_template('add_student.html')

@app.route('/record_activity')
@login_required
def record_activity_page():
    return render_template('record_activity.html')

@app.route('/activity')
@login_required
@admin_required
def activity_form():
    return render_template('add_activity.html')

@app.route('/students')
@login_required
def students_page():
    return render_template('students.html')

@app.route('/student/<int:student_id>')
@login_required
def student_profile(student_id):
    return render_template('student_profile.html', student_id=student_id)

@app.route('/student_history/<int:student_id>')
@login_required
def student_history_page(student_id):
    return render_template('student_history.html', student_id=student_id)

@app.route('/logs')
@login_required
@admin_required
def logs_page():
    return render_template('logs.html')

@app.route('/prizes')
@login_required
@admin_required
def prizes_page():
    return render_template('prizes.html')

@app.route('/redeem')
@login_required
def redeem_page():
    return render_template('redeem.html')
    
@app.route('/audit_logs')
@login_required
@admin_required
def audit_logs_page():
    return render_template('audit_logs.html')
    
@app.route('/help')
@login_required
def help_page():
    return render_template('help.html')
    
    
# ---- PASSWORD MANAGEMENT ROUTES (Added) ----

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pass = request.form.get('current_password')
        new_pass = request.form.get('new_password')
        confirm_pass = request.form.get('confirm_password')
        username = session['username']

        if new_pass != confirm_pass:
            return render_template('change_password.html', error="New passwords do not match")

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            # Verify old password
            cur.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            
            if user:
                stored_hash = user['password_hash'] if isinstance(user, dict) else user[0]
                
                if check_password_hash(stored_hash, current_pass):
                    # Update to new password
                    new_hash = generate_password_hash(new_pass)
                    cur.execute("UPDATE users SET password_hash = %s WHERE username = %s", (new_hash, username))
                    
                    # --- LOG AUDIT EVENT ---
                    transaction_manager.log_audit_event(
                        action_type="PASSWORD_CHANGE",
                        details=f"User changed their own password",
                        recorded_by=username
                    )

                    conn.commit()
                    return render_template('change_password.html', success="Password changed successfully!")
                else:
                    return render_template('change_password.html', error="Current password is incorrect")
            
            return render_template('change_password.html', error="User not found")
        finally:
            conn.close()

    return render_template('change_password.html')



@app.route('/admin/reset_password', methods=['POST'])
@login_required
def admin_reset_password():
    current_role = session.get('role')
    staff_identity = session.get('username', 'system') # Capture the actor
    
    # ALLOW both sysadmin and admin
    if current_role not in ['sysadmin', 'admin']:
        return redirect(url_for('index'))

    user_id = request.form.get('user_id')
    new_pass = request.form.get('new_pass')
    
    if not new_pass or len(new_pass) < 4:
         return redirect(url_for('manage_users', msg="Error: Password must be at least 4 characters."))

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # --- SECURITY CHECK ---
        # Fetch the target user's role before updating
        cur.execute("SELECT role, username FROM users WHERE id = %s", (user_id,))
        target = cur.fetchone()
        
        if not target:
            return redirect(url_for('manage_users', msg="Error: User not found."))
            
        target_role = target['role'] if isinstance(target, dict) else target[0]
        target_username = target['username'] if isinstance(target, dict) else target[1]

        # Rule: Standard 'admin' cannot reset a 'sysadmin' password
        if current_role != 'sysadmin' and target_role == 'sysadmin':
            return redirect(url_for('manage_users', msg="Access Denied: You cannot modify SysAdmin accounts."))

        # Proceed with update
        new_hash = generate_password_hash(new_pass)
        cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
        
        # --- LOG AUDIT EVENT ---
        transaction_manager.log_audit_event(
            action_type="ADMIN_PASSWORD_RESET",
            details=f"Forced password reset for user: {target_username}",
            recorded_by=staff_identity
        )

        conn.commit()
        return redirect(url_for('manage_users', msg=f"Success: Password reset for {target_username}."))
        
    except Exception as e:
        conn.rollback()
        logger.exception(f"Password reset failed: {e}")
        return redirect(url_for('manage_users', msg=f"System Error: {str(e)}"))
    finally:
        conn.close()


@app.route('/admin/users/create', methods=['POST'])
@login_required
def create_user():
    current_role = session.get('role')
    staff_identity = session.get('username', 'system')
    
    # 1. Access Control
    if current_role not in ['sysadmin', 'admin']:
        return redirect(url_for('index'))

    # 2. Get Form Data
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role')

    # 3. Validation
    if not username or not password or not role:
        return redirect(url_for('manage_users', msg="Error: All fields are required."))
    
    if len(password) < 4:
        return redirect(url_for('manage_users', msg="Error: Password must be at least 4 characters."))

    # 4. Role Hierarchy Check
    # An 'admin' cannot create a 'sysadmin'
    if current_role != 'sysadmin' and role == 'sysadmin':
        return redirect(url_for('manage_users', msg="Access Denied: You cannot create SysAdmin accounts."))
    
    # 5. DB Operation
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Check for duplicates
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            return redirect(url_for('manage_users', msg=f"Error: User '{username}' already exists."))

        # Create User
        hashed_pw = generate_password_hash(password)
        cur.execute("""
            INSERT INTO users (username, password_hash, role)
            VALUES (%s, %s, %s)
        """, (username, hashed_pw, role))
        
        # 6. Audit Log
        transaction_manager.log_audit_event(
            action_type="CREATE_USER",
            details=f"Created new user '{username}' with role '{role}'",
            recorded_by=staff_identity
        )

        conn.commit()
        return redirect(url_for('manage_users', msg=f"Success: User '{username}' created."))

    except Exception as e:
        conn.rollback()
        logger.exception(f"Create user failed: {e}")
        return redirect(url_for('manage_users', msg=f"System Error: {str(e)}"))
    finally:
        conn.close()
# ---- Student Management API ----

@app.route('/api/add_student', methods=['POST'])
@login_required
def api_add_student():
    data = request.get_json() or {}
    staff_identity = session.get('username', 'system')
    
    student_data = {
        'full_name': data.get('full_name'),
        'nickname': data.get('nickname'),
        'phone': data.get('phone'),
        'email': data.get('email'),
        'parent_name': data.get('parent_name'),
        'classroom': data.get('classroom'),
        'grade': data.get('grade'),
        'sms_consent': str(data.get('sms_consent', '')).lower() in ('1', 'true', 'yes', 'on')
    }
    
    if not student_data['full_name']:
        return jsonify({"success": False, "message": "Full name is required."}), 400
    
    success, message = add_student.add_new_student(student_data)
    
    if success:
        transaction_manager.log_audit_event(
            action_type="CREATE_STUDENT",
            details=f"Added student: {student_data['full_name']} (Class: {student_data['classroom']})",
            recorded_by=staff_identity
        )
        logger.info(f"Student created: {student_data['full_name']} by {staff_identity}")
        return jsonify({"success": True, "message": message}), 201
    else:
        logger.error(f"Student creation failed: {message}")
        return jsonify({"success": False, "message": message}), 400
        

# ---- Edit Student Functionality ----

@app.route('/student/<int:student_id>/edit')
@login_required
def edit_student_page(student_id):
    return render_template('edit_student.html', student_id=student_id)


@app.route('/api/student/<int:student_id>/update', methods=['POST'])
@login_required
def api_update_student(student_id):
    data = request.get_json() or {}
    staff_identity = session.get('username', 'system')

    # Validate required fields
    if not data.get('full_name'):
        return jsonify({"success": False, "message": "Full Name is required."}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Check if student exists
        cur.execute("SELECT full_name FROM students WHERE id = %s", (student_id,))
        existing = cur.fetchone()
        if not existing:
            return jsonify({"success": False, "message": "Student not found."}), 404

        # --- UPDATED QUERY with 'active' ---
        cur.execute("""
            UPDATE students 
            SET full_name = %s,
                nickname = %s,
                grade = %s,
                classroom = %s,
                parent_name = %s,
                phone = %s,
                email = %s,
                sms_consent = %s,
                active = %s
            WHERE id = %s
        """, (
            data['full_name'],
            data.get('nickname'),
            data.get('grade'),
            data.get('classroom'),
            data.get('parent_name'),
            data.get('phone'),
            data.get('email'),
            bool(data.get('sms_consent')),
            bool(data.get('active', True)), # Defaults to True if missing
            student_id
        ))

        # Log the change
        transaction_manager.log_audit_event(
            action_type="UPDATE_STUDENT",
            details=f"Updated details for student ID {student_id} ({data['full_name']})",
            recorded_by=staff_identity
        )

        conn.commit()
        return jsonify({"success": True, "message": "Student updated successfully!"}), 200

    except Exception as e:
        conn.rollback()
        logger.exception(f"Error updating student {student_id}: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()



@app.route('/api/check_duplicates', methods=['POST'])
@login_required
def api_check_duplicates():
    data = request.get_json() or {}
    name = data.get('name', '')
    
    results = student_search.find_students(name)
    
    matches = []
    for s in results:
        is_dict = isinstance(s, dict)
        s_name = s['full_name'] if is_dict else s[1]
        if name.lower() in s_name.lower():
            matches.append(s)
    
    return jsonify({"matches": matches}), 200

@app.route('/api/student/<int:student_id>', methods=['GET'])
@login_required
def api_get_student_details(student_id):
    try:
        student = student_search.get_student_by_id(student_id) 
        if student is None:
            return jsonify({"success": False, "message": f"Student {student_id} not found."}), 404
        return jsonify({"success": True, "student": student}), 200
    except Exception as e:
        logger.exception(f"Error fetching student {student_id}: {e}")
        return jsonify({"success": False, "message": str(e)}), 500



@app.route('/api/students/search', methods=['GET'])
@login_required
def api_students_search():
    search_term = request.args.get('term', '').strip()
    
    # Existing flag
    include_inactive = request.args.get('include_inactive') == 'true'
    
    # NEW: Check for show_all flag
    show_all = request.args.get('show_all') == 'true'

    # LOGIC UPDATE: Only enforce minimum length if we are NOT showing all
    if not show_all and len(search_term) < 2:
        return jsonify({"success": True, "students": []}), 200 

    try:
        # Pass the new show_all flag to the search logic
        students = student_search.find_students(
            search_term, 
            include_inactive=include_inactive,
            show_all=show_all
        )
        return jsonify({"success": True, "students": students}), 200 
    except Exception as e:
        # Using app.logger if logger isn't globally defined in this scope, 
        # or keep logger.exception if that's how your imports are set up.
        try:
            logger.exception(f"Search error: {e}")
        except:
            current_app.logger.error(f"Search error: {e}")
            
        return jsonify({"success": False, "message": str(e)}), 500
        
        


# ---- Transaction API  ----

@app.route('/api/transaction/record', methods=['POST'])
@login_required
def api_record_transaction():
    data = request.get_json(silent=True)
    if not data: 
        return jsonify({"success": False, "message": "Invalid JSON"}), 400

    student_id = data.get('student_id')
    activity_name = data.get('activity_name', 'Manual Entry')
    # --- NEW: Capture ID ---
    activity_id = data.get('activity_id') 
    # -----------------------
    points = data.get('points')
    
    if not student_id or points is None:
        return jsonify({"success": False, "message": "Missing Data"}), 400

    staff_identity = session.get('username', 'system')

    success, msg = transaction_manager.add_points(
        student_id=student_id,
        points=int(points),
        activity_type=activity_name,
        description=data.get('description', ''),
        recorded_by=staff_identity,
        # --- NEW: Pass to DB ---
        activity_id=activity_id 
        # -----------------------
    )
    
    if success:
        return jsonify({"success": True, "message": msg}), 200
    else:
        return jsonify({"success": False, "message": msg}), 500


@app.route('/api/student/<int:student_id>/history', methods=['GET'])
@login_required
def api_student_history(student_id):
    try:
        student = student_search.get_student_by_id(student_id)
        if not student:
            return jsonify({"success": False, "message": "Student not found"}), 404

        rows = transaction_manager.get_student_transactions(student_id)
        
        history = []
        for row in rows:
            is_dict = isinstance(row, dict)
            history.append({
                "id": row['id'] if is_dict else row[0],
                "timestamp": row['timestamp'] if is_dict else row[1],
                "activity_type": row['activity_type'] if is_dict else row[2],
                "points": row['points'] if is_dict else row[3],
                "description": row['description'] if is_dict else row[4],
                "recorded_by": row['recorded_by'] if is_dict else row[5]
            })
        total = transaction_manager.get_student_balance(student_id)

        return jsonify({
            "success": True,
            "student_name": student['full_name'],
            "total_points": total,
            "history": history
        }), 200
    except Exception as e:
        logger.exception(f"History error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/reports/students/csv')
@login_required
def download_all_students_csv():
    import csv
    import io
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Fetch all students with their live point balance
        cur.execute("""
            SELECT s.id, s.full_name, s.nickname, s.grade, s.classroom, 
                   s.parent_name, s.email, s.phone, s.sms_consent,
                   COALESCE(SUM(al.points), 0) as total_points
            FROM students s
            LEFT JOIN activity_log al ON s.id = al.student_id
            GROUP BY s.id
            ORDER BY s.grade ASC, s.classroom ASC, s.full_name ASC
        """)
        rows = cur.fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # CSV Headers
        writer.writerow([
            'Student ID', 'Full Name', 'Nickname', 'Grade', 'Classroom', 
            'Parent Name', 'Email', 'Phone', 'SMS Consent', 'Total Points'
        ])
        
        for row in rows:
            is_dict = isinstance(row, dict)
            writer.writerow([
                row['id'] if is_dict else row[0],
                row['full_name'] if is_dict else row[1],
                row['nickname'] if is_dict else row[2],
                row['grade'] if is_dict else row[3],
                row['classroom'] if is_dict else row[4],
                row['parent_name'] if is_dict else row[5],
                row['email'] if is_dict else row[6],
                row['phone'] if is_dict else row[7],
                'Yes' if (row['sms_consent'] if is_dict else row[8]) else 'No',
                row['total_points'] if is_dict else row[9]
            ])
            
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"All_Students_{datetime.datetime.now().strftime('%Y-%m-%d')}.csv"
        )
    except Exception as e:
        logger.exception(f"Export error: {e}")
        return f"Error exporting CSV: {e}", 500
    finally:
        conn.close()


# ---- ACTIVITY RELATED ROUTES ----

@app.route('/api/add_activity', methods=['POST'])
@login_required
@admin_required
def api_create_activity():
    data = request.get_json() or {}
    name = data.get('name')
    desc = data.get('description', '')
    pts = data.get('default_points', 0)
    is_active = bool(int(data.get('active', 1)))
    
    # 1. Capture the user identity
    staff_identity = session.get('username', 'system')

    if not name:
        return jsonify({"success": False, "message": "Name is required"}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # 2. Check existence first to distinguish Create vs Update for the Audit Log
        cur.execute("SELECT id FROM activities WHERE name = %s", (name,))
        existing = cur.fetchone()
        
        action_type = "UPDATE_ACTIVITY" if existing else "CREATE_ACTIVITY"
        log_details = f"{'Updated' if existing else 'Created'} activity '{name}': Pts={pts}, Active={is_active}"

        # 3. Perform the Upsert (Insert or Update)
        cur.execute("""
            INSERT INTO activities (name, description, default_points, active)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                description = EXCLUDED.description,
                default_points = EXCLUDED.default_points,
                active = EXCLUDED.active
        """, (name, desc, pts, is_active))
        
        # 4. Log to Audit Trail
        transaction_manager.log_audit_event(
            action_type=action_type,
            details=log_details,
            recorded_by=staff_identity
        )

        conn.commit()
        return jsonify({"success": True, "message": "Activity saved"}), 200
    except Exception as e:
        logger.exception(f"Error saving activity: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()



@app.route('/api/activity', methods=['GET'])
@login_required
def api_list_activities():
    """Returns simplified activity list for dropdowns (Record Activity page)."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "DB Connection Error"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, default_points FROM activities WHERE active = TRUE ORDER BY name")
        rows = cur.fetchall()
        activities = []
        for row in rows:
            is_dict = isinstance(row, dict)
            activities.append({
                "id": row['id'] if is_dict else row[0],
                "name": row['name'] if is_dict else row[1],
                "default_points": row['default_points'] if is_dict else row[2]
            })
        return jsonify(activities), 200
    except Exception as e:
        logger.exception(f"Error fetching activities for dropdown: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/list_activities', methods=['GET'])
@login_required
def api_list_all_activities():
    """Returns all activities for the manager."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "DB Connection Error"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, description, default_points, active FROM activities ORDER BY name ASC")
        rows = cur.fetchall()
        activities = []
        for row in rows:
            activities.append({
                "id": row['id'] if isinstance(row, dict) else row[0],
                "name": row['name'] if isinstance(row, dict) else row[1],
                "description": row['description'] if isinstance(row, dict) else row[2],
                "default_points": row['default_points'] if isinstance(row, dict) else row[3],
                "active": row['active'] if isinstance(row, dict) else row[4]
            })
        return jsonify({"activities": activities}), 200
    except Exception as e:
        logger.exception(f"Error listing activities: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()
        

@app.route('/api/activity/delete/<int:activity_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_activity(activity_id):
    staff_identity = session.get('username', 'system')
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM activities WHERE id = %s", (activity_id,))
        act = cur.fetchone()
        if not act:
            return jsonify({"success": False, "message": "Activity not found"}), 404
        
        act_name = act['name'] if isinstance(act, dict) else act[0]

        cur.execute("SELECT COUNT(*) FROM activity_log WHERE activity_type = %s", (act_name,))
        count = cur.fetchone()
        log_count = count['count'] if isinstance(count, dict) else count[0]

        if log_count > 0:
            return jsonify({
                "success": False, 
                "message": f"Cannot delete '{act_name}' because it has {log_count} transactions. Set it to 'Inactive' instead."
            }), 400

        cur.execute("DELETE FROM activities WHERE id = %s", (activity_id,))
        
        # 1. Log to Audit Trail
        transaction_manager.log_audit_event(
            action_type="DELETE_ACTIVITY",
            details=f"Deleted activity '{act_name}' (ID: {activity_id})",
            recorded_by=staff_identity
        )
        
        conn.commit()
        return jsonify({"success": True, "message": "Activity deleted successfully"}), 200
    finally:
        conn.close()



# ---- Log Management ----

@app.route('/api/logs/view')
@login_required
@admin_required
def api_view_logs():
    if not os.path.exists(LOG_PATH):
        return jsonify({'logs': ['Log file is empty or does not exist.']})
    try:
        with open(LOG_PATH, 'r') as f:
            lines = f.readlines()
            last_lines = lines[-50:] if len(lines) > 50 else lines
            return jsonify({'logs': last_lines})
    except Exception as e:
        return jsonify({'logs': [f"Error reading log: {str(e)}"]})

@app.route('/api/logs/download')
@login_required
@admin_required
def download_logs():
    if not os.path.exists(LOG_PATH):
        abort(404, description="Log file not found.")
    try:
        return send_file(LOG_PATH, as_attachment=True, download_name=f"leermexico_logs.txt")
    except Exception as e:
        app.logger.exception(f"Error downloading log: {e}")
        abort(500)
        
@app.route('/api/logs/clear', methods=['POST'])
@login_required
@admin_required
def clear_logs():
    staff_identity = session.get('username', 'system')
    backup_file = f"{LOG_PATH}.bak.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    try:
        # --- LOG AUDIT EVENT (DB) ---
        # We log this to the database because the file log is about to be rotated/cleared
        transaction_manager.log_audit_event(
            action_type="CLEAR_LOGS",
            details=f"System logs manually cleared/rotated. Archived to {os.path.basename(backup_file)}",
            recorded_by=staff_identity
        )

        root_logger = logging.getLogger()
        file_handler_found = None
        for h in root_logger.handlers:
            if isinstance(h, RotatingFileHandler):
                file_handler_found = h
                break
        
        if file_handler_found:
            file_handler_found.close()
            root_logger.removeHandler(file_handler_found)

        if os.path.exists(LOG_PATH):
            os.rename(LOG_PATH, backup_file)
        
        # Re-initialize
        new_handler = RotatingFileHandler(LOG_PATH, maxBytes=500000, backupCount=3)
        new_handler.setLevel(logging.INFO)
        new_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        root_logger.addHandler(new_handler)
        
        root_logger.info(f"Log file rotated. Archived as {os.path.basename(backup_file)}")
        return jsonify({'success': True, 'message': 'Logs cleared successfully.'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})        
        

# ---- Prize Management API ----

@app.route('/api/prizes/add', methods=['POST'])
@login_required
@admin_required
def api_add_prize():
    data = request.get_json() or {}
    name = data.get('name')
    cost = data.get('point_cost', 0)
    stock = data.get('stock_count', 0)
    active = bool(int(data.get('active', 1)))
    
    staff_identity = session.get('username', 'system')

    if not name:
        return jsonify({"success": False, "message": "Prize name is required"}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # 1. DIFFERENTIATION CHECK:
        # Check if the prize exists BEFORE we write to the DB.
        cur.execute("SELECT id FROM prize_inventory WHERE name = %s", (name,))
        existing = cur.fetchone()
        
        # 2. Set the Log Type based on the result
        if existing:
            action_type = "UPDATE_PRIZE"
            log_details = f"Updated prize '{name}': Cost={cost}, Stock={stock}, Active={active}"
        else:
            action_type = "CREATE_PRIZE"
            log_details = f"Created new prize '{name}': Cost={cost}, Stock={stock}, Active={active}"

        # 3. Perform the Upsert (Safe to do now)
        cur.execute("""
            INSERT INTO prize_inventory (name, description, point_cost, stock_count, active)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                point_cost = EXCLUDED.point_cost,
                stock_count = EXCLUDED.stock_count,
                active = EXCLUDED.active,
                description = EXCLUDED.description
        """, (name, data.get('description', ''), cost, stock, active))
        
        # 4. Log the specific event
        transaction_manager.log_audit_event(
            action_type=action_type,
            details=log_details,
            recorded_by=staff_identity
        )
        
        conn.commit()
        return jsonify({"success": True, "message": f"Prize '{name}' saved successfully"}), 200
    except Exception as e:
        if conn: conn.rollback()
        logger.exception(f"Error saving prize: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/prizes', methods=['GET'])
@login_required
def api_list_prizes():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, description, point_cost, stock_count, active FROM prize_inventory ORDER BY name ASC")
        rows = cur.fetchall()
        prizes = []
        for row in rows:
            is_dict = isinstance(row, dict)
            prizes.append({
                "id": row['id'] if is_dict else row[0],
                "name": row['name'] if is_dict else row[1],
                "description": row['description'] if is_dict else row[2],
                "point_cost": row['point_cost'] if is_dict else row[3],
                "stock_count": row['stock_count'] if is_dict else row[4],
                "active": row['active'] if is_dict else row[5]
            })
        return jsonify({"prizes": prizes}), 200
    finally:
        conn.close()

@app.route('/api/prizes/redeem', methods=['POST'])
@login_required
def api_redeem_prize():
    data = request.get_json() or {}
    student_id = data.get('student_id')
    prize_id = data.get('prize_id')
    
    staff_identity = session.get('username', 'system')

    if not student_id or not prize_id:
        return jsonify({"success": False, "message": "Missing student or prize ID"}), 400

    # CORRECT: Delegate to the manager.
    # This ensures "REDEEM_POINTS" is used for the audit log.
    success, msg = transaction_manager.redeem_prize_logic(student_id, prize_id, staff_identity)

    if success:
        return jsonify({"success": True, "message": msg}), 200
    else:
        # Pass 400 for logic errors (funds/stock), 500 is handled by the manager's crash handler
        return jsonify({"success": False, "message": msg}), 400



@app.route('/api/prizes/delete/<int:prize_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_prize(prize_id):
    staff_identity = session.get('username', 'system')
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM prize_inventory WHERE id = %s", (prize_id,))
        prz = cur.fetchone()
        if not prz:
            return jsonify({"success": False, "message": "Prize not found"}), 404
        
        prize_name = prz['name'] if isinstance(prz, dict) else prz[0]

        # Check for dependencies (redemptions)
        redemption_str = f"Redemption: {prize_name}"
        cur.execute("SELECT COUNT(*) FROM activity_log WHERE activity_type = %s", (redemption_str,))
        count = cur.fetchone()
        log_count = count['count'] if isinstance(count, dict) else count[0]

        if log_count > 0:
            return jsonify({
                "success": False, 
                "message": f"Cannot delete '{prize_name}' because it has {log_count} redemptions. Set it to 'Inactive' instead."
            }), 400

        # Delete the prize
        cur.execute("DELETE FROM prize_inventory WHERE id = %s", (prize_id,))
        
        # 1. Log to Audit Trail
        transaction_manager.log_audit_event(
            action_type="DELETE_PRIZE",
            details=f"Deleted prize '{prize_name}' (ID: {prize_id})",
            recorded_by=staff_identity
        )

        conn.commit()
        return jsonify({"success": True, "message": "Prize deleted successfully"}), 200
    finally:
        conn.close()


# ---- Audit Log API ----

@app.route('/api/logs/audit')
@login_required
@admin_required
def api_view_audit_logs_data():
    # Get parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search_term = request.args.get('search')

    conn = get_db_connection()
    if not conn: return jsonify({"success": False}), 500
    
    try:
        cur = conn.cursor()
        
        # Build Query Dynamically
        sql = "SELECT id, action_type, details, recorded_by, event_time FROM audit_log WHERE 1=1"
        params = []

        if start_date:
            sql += " AND event_time::DATE >= %s"
            params.append(start_date)
        
        if end_date:
            sql += " AND event_time::DATE <= %s"
            params.append(end_date)
        
        if search_term:
            sql += " AND (details ILIKE %s OR action_type ILIKE %s OR recorded_by ILIKE %s)"
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern, search_pattern, search_pattern])
            
        sql += " ORDER BY event_time DESC LIMIT 500"

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        
        audit_history = []
        for row in rows:
            is_dict = isinstance(row, dict)
            audit_history.append({
                "id": row['id'] if is_dict else row[0],
                "action": row['action_type'] if is_dict else row[1],
                "details": row['details'] if is_dict else row[2],
                "user": row['recorded_by'] if is_dict else row[3],
                "timestamp": row['event_time'] if is_dict else row[4]
            })
        return jsonify({"success": True, "logs": audit_history}), 200
    finally:
        conn.close()

@app.route('/api/logs/audit/csv')
@login_required
@admin_required
def download_audit_logs_csv():
    import csv
    import io
    
    # 1. Fetch Filters (Mirrors api_view_audit_logs_data)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search_term = request.args.get('search')

    conn = get_db_connection()
    if not conn:
        return "Database Connection Error", 500
    
    try:
        cur = conn.cursor()
        
        # 2. Build Query 
        # We reorder columns slightly for a better CSV layout (Time first)
        sql = "SELECT id, event_time, action_type, recorded_by, details FROM audit_log WHERE 1=1"
        params = []

        if start_date:
            sql += " AND event_time::DATE >= %s"
            params.append(start_date)
        
        if end_date:
            sql += " AND event_time::DATE <= %s"
            params.append(end_date)
        
        if search_term:
            sql += " AND (details ILIKE %s OR action_type ILIKE %s OR recorded_by ILIKE %s)"
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern, search_pattern, search_pattern])
            
        # We REMOVE the LIMIT 500 here so the CSV contains the full dataset matching the filters
        sql += " ORDER BY event_time DESC"

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        
        # 3. Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Headers
        writer.writerow(['ID', 'Timestamp', 'Action', 'User', 'Details'])
        
        for row in rows:
            is_dict = isinstance(row, dict)
            writer.writerow([
                row['id'] if is_dict else row[0],
                row['event_time'] if is_dict else row[1],
                row['action_type'] if is_dict else row[2],
                row['recorded_by'] if is_dict else row[3],
                row['details'] if is_dict else row[4]
            ])
            
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"Audit_Logs_{datetime.datetime.now().strftime('%Y-%m-%d')}.csv"
        )
    except Exception as e:
        logger.exception(f"Export audit CSV error: {e}")
        return f"Error exporting CSV: {e}", 500
    finally:
        conn.close()
    
# ---- 11. Reporting (View & CSV) ----

# 1. Redemption Report
@app.route('/reports/redemptions')
@login_required
@admin_required
def view_redemptions_report():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Query for display
        cur.execute("""
            SELECT al.timestamp, s.full_name, s.grade, s.classroom, 
                   al.activity_type, al.points, al.recorded_by
            FROM activity_log al
            JOIN students s ON al.student_id = s.id
            WHERE al.activity_type LIKE 'Redemption:%'
            ORDER BY al.timestamp DESC
        """)
        rows = cur.fetchall()
        
        # Normalize data for template
        data = []
        for row in rows:
            is_dict = isinstance(row, dict)
            data.append({
                'timestamp': row['timestamp'] if is_dict else row[0],
                'full_name': row['full_name'] if is_dict else row[1],
                'grade': row['grade'] if is_dict else row[2],
                'classroom': row['classroom'] if is_dict else row[3],
                'activity_type': row['activity_type'] if is_dict else row[4],
                'points': row['points'] if is_dict else row[5],
                'recorded_by': row['recorded_by'] if is_dict else row[6]
            })
        return render_template('report_redemptions.html', rows=data)
    finally:
        conn.close()

@app.route('/api/reports/redemptions/csv')
@login_required
@admin_required
def download_redemption_csv():
    import csv
    import io
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT al.timestamp, s.full_name, s.grade, s.classroom, 
                   al.activity_type, al.points, al.recorded_by
            FROM activity_log al
            JOIN students s ON al.student_id = s.id
            WHERE al.activity_type LIKE 'Redemption:%'
            ORDER BY al.timestamp DESC
        """)
        rows = cur.fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Date', 'Student', 'Grade', 'Classroom', 'Prize', 'Points', 'Staff'])
        
        for row in rows:
            is_dict = isinstance(row, dict)
            writer.writerow([
                row['timestamp'] if is_dict else row[0],
                row['full_name'] if is_dict else row[1],
                row['grade'] if is_dict else row[2],
                row['classroom'] if is_dict else row[3],
                row['activity_type'] if is_dict else row[4],
                row['points'] if is_dict else row[5],
                row['recorded_by'] if is_dict else row[6]
            ])
            
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"Redemptions_{datetime.datetime.now().strftime('%Y-%m-%d')}.csv"
        )
    finally:
        conn.close()

# 2. Inventory Report
@app.route('/reports/inventory')
@login_required
@admin_required
def view_inventory_report():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name, point_cost, stock_count, active, description FROM prize_inventory ORDER BY name")
        rows = cur.fetchall()
        
        data = []
        for row in rows:
            is_dict = isinstance(row, dict)
            data.append({
                'name': row['name'] if is_dict else row[0],
                'point_cost': row['point_cost'] if is_dict else row[1],
                'stock_count': row['stock_count'] if is_dict else row[2],
                'active': row['active'] if is_dict else row[3],
                'description': row['description'] if is_dict else row[4]
            })
        return render_template('report_inventory.html', rows=data)
    finally:
        conn.close()

@app.route('/api/reports/inventory/csv')
@login_required
@admin_required
def download_inventory_csv():
    import csv
    import io
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name, point_cost, stock_count, active, description FROM prize_inventory ORDER BY name")
        rows = cur.fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Prize Name', 'Cost', 'Stock', 'Status', 'Description'])
        
        for row in rows:
            is_dict = isinstance(row, dict)
            writer.writerow([
                row['name'] if is_dict else row[0],
                row['point_cost'] if is_dict else row[1],
                row['stock_count'] if is_dict else row[2],
                'Active' if (row['active'] if is_dict else row[3]) else 'Inactive',
                row['description'] if is_dict else row[4]
            ])
            
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"Inventory_{datetime.datetime.now().strftime('%Y-%m-%d')}.csv"
        )
    finally:
        conn.close()


if __name__ == '__main__':
    # Check the environment variable. Default to False (Production safety)
    is_debug = os.getenv('FLASK_DEBUG', '0') == '1'

    if is_debug:
        logger.info("Starting in DEVELOPMENT mode (Debug ON)")
    else:
        logger.info("Starting in PRODUCTION mode")

    app.run(debug=is_debug, port=5000)
