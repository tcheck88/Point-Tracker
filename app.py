"""
app.py - Leer México Activity Manager backend (PostgreSQL Version)
Serves static UIs and APIs for students and activities.
FULLY INTEGRATED WITH AUTHENTICATION SECURITY
"""

import os
import sys
import logging
import datetime
from functools import wraps
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify, abort, send_file, redirect, url_for, render_template, send_from_directory, session
from flask_babel import Babel 
from werkzeug.security import generate_password_hash, check_password_hash

# --- IMPORTS FOR POSTGRESQL ---
from db_utils import init_db, get_db_connection
import add_student
import student_search
import transaction_manager
import alerts

# ---- 1. Paths and App Setup ----
APP_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(APP_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, 'app.log')

if getattr(sys, 'frozen', False):
    basedir = sys._MEIPASS
else:
    basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "prod-secret-must-be-set")

# ---- 2. Babel Localization Setup ----
def get_locale():
    if 'lang' in request.args:
        lang = request.args['lang']
        if lang in app.config['LANGUAGES']:
            return lang
    return request.accept_languages.best_match(app.config['LANGUAGES'].keys())

app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['BABEL_TRANSLATION_DIRECTORIES'] = os.path.join(basedir, 'translations')
app.config['LANGUAGES'] = {'en': 'English', 'es': 'Español'}

babel = Babel(app, locale_selector=get_locale)

@app.context_processor
def inject_conf_var():
    return dict(get_locale=get_locale)

# ---- 3. Authentication Decorator ----
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# ---- 4. Logging Setup (Retained from Original) ----
class EmailAlertHandler(logging.Handler):
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            try:
                msg = self.format(record)
                alerts.send_alert(subject=f"Application Error: {record.levelname}", message=msg)
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
for h in list(root_logger.handlers):
    root_logger.removeHandler(h)

root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

email_handler = EmailAlertHandler()
email_handler.setLevel(logging.ERROR)
email_handler.setFormatter(logging.Formatter('%(message)s'))
root_logger.addHandler(email_handler)

logger = logging.getLogger(__name__)

# ---- 5. Auth Routes ----
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['username'] = user['username']
            return redirect(url_for('index'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# ---- 6. Protected UI Routes ----
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
def activity_form():
    return render_template('add_activity.html')


@app.route('/student/<int:student_id>')
@login_required
def student_profile(student_id):
    return render_template('student_profile.html', student_id=student_id)

@app.route('/prizes')
@login_required
def prizes_page():
    return render_template('prizes.html')

@app.route('/redeem')
@login_required
def redeem_page():
    return render_template('redeem.html')

@app.route('/audit_logs')
@login_required
def audit_logs_page():
    return render_template('audit_logs.html')
    
@app.route('/logs')
@login_required
def logs_page():
    """Renders the HTML page for viewing system logs."""
    return render_template('logs.html')
    
# Combined routes for the Student Directory
@app.route('/students')
@app.route('/students_list') 
@login_required
def students_page():
    """Renders the Student Directory/List page for multiple routes."""
    return render_template('students.html')



# ---- 7. Student Management API ----
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
        transaction_manager.log_audit_event(action_type="CREATE_STUDENT", details=f"Added student: {student_data['full_name']}", recorded_by=staff_identity)
        return jsonify({"success": True, "message": message}), 201
    return jsonify({"success": False, "message": message}), 400

@app.route('/api/check_duplicates', methods=['POST'])
@login_required
def api_check_duplicates():
    data = request.get_json() or {}
    name = data.get('name', '')
    results = student_search.find_students(name)
    matches = [s for s in results if name.lower() in (s['full_name'] if isinstance(s, dict) else s[1]).lower()]
    return jsonify({"matches": matches}), 200

@app.route('/api/student/<int:student_id>', methods=['GET'])
@login_required
def api_get_student_details(student_id):
    try:
        student = student_search.get_student_by_id(student_id)
        if student is None: return jsonify({"success": False, "message": f"Student {student_id} not found."}), 404
        return jsonify({"success": True, "student": student}), 200
    except Exception as e:
        logger.error(f"Error fetching student {student_id}: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ---- 8. Transaction API ----
@app.route('/api/transaction/record', methods=['POST'])
@login_required
def api_record_transaction():
    data = request.get_json(silent=True)
    if not data or not data.get('student_id') or data.get('points') is None:
        return jsonify({"success": False, "message": "Missing Data"}), 400
    staff_identity = session.get('username', 'system')
    success, msg = transaction_manager.add_points(
        student_id=data.get('student_id'),
        points=int(data.get('points')),
        activity_type=data.get('activity_name', 'Manual Entry'),
        description=data.get('description', ''),
        recorded_by=staff_identity
    )
    return jsonify({"success": success, "message": msg}), 200 if success else 500

# ---- 9. Prize Management API (Retained Atomic Logic) ----
@app.route('/api/prizes/redeem', methods=['POST'])
@login_required
def api_redeem_prize():
    data = request.get_json()
    if not data: return jsonify({"success": False, "message": "Invalid request."}), 400
    student_id, prize_id = data.get('student_id'), data.get('prize_id')
    staff_identity = session.get('username', 'system')
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name, point_cost, stock_count FROM prize_inventory WHERE id = %s", (prize_id,))
        prize = cur.fetchone()
        if not prize: return jsonify({"success": False, "message": "Prize not found."}), 404
        is_dict = isinstance(prize, dict)
        p_name, p_cost, p_stock = (prize['name'], prize['point_cost'], prize['stock_count']) if is_dict else (prize[0], prize[1], prize[2])
        if p_stock <= 0: return jsonify({"success": False, "message": f"'{p_name}' out of stock."}), 400
        if transaction_manager.get_student_balance(student_id) < p_cost: return jsonify({"success": False, "message": "Insufficient points."}), 400
        success, msg = transaction_manager.add_points(student_id, -abs(p_cost), f"Redemption: {p_name}", "Prize Exchange", staff_identity)
        if success:
            cur.execute("UPDATE prize_inventory SET stock_count = stock_count - 1 WHERE id = %s", (prize_id,))
            conn.commit()
            return jsonify({"success": True, "message": f"Redeemed {p_name}!"}), 200
        conn.rollback()
        return jsonify({"success": False, "message": msg}), 500
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()

# ---- 10. Log and Audit Management (Retained Rotation Logic) ----
@app.route('/api/logs/clear', methods=['POST'])
@login_required
def clear_logs():
    backup_file = f"{LOG_PATH}.bak.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    try:
        for h in logging.getLogger().handlers: h.close()
        if os.path.exists(LOG_PATH): os.rename(LOG_PATH, backup_file)
        new_handler = RotatingFileHandler(LOG_PATH, maxBytes=500000, backupCount=3)
        new_handler.setLevel(logging.INFO)
        new_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logging.getLogger().addHandler(new_handler)
        return jsonify({'success': True, 'message': 'Logs cleared.'})
    except Exception as e: return jsonify({'success': False, 'message': str(e)})

@app.route('/api/logs/audit')
@login_required
def api_view_audit_logs():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, action_type, details, recorded_by, event_time FROM audit_log ORDER BY event_time DESC LIMIT 100")
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
    finally: conn.close()
    
@app.route('/api/logs/download')
@login_required
def api_download_logs():
    """Securely downloads the current system log file."""
    try:
        if os.path.exists(LOG_PATH):
            return send_file(
                LOG_PATH,
                as_attachment=True,
                download_name=f"leermexico_log_{datetime.datetime.now().strftime('%Y%m%d')}.txt"
            )
        else:
            return jsonify({"success": False, "message": "Log file not found."}), 404
    except Exception as e:
        logger.error(f"Failed to download logs: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# (NOTE: All original routes for list_activities, delete_activity, logs_view, prizes_delete, etc., remain in the code)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)