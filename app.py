"""
app.py - Leer México Activity Manager backend (PostgreSQL Version)
Final Merged Production Version
Includes: Auth, Student Directory, Search, History, Activity Management, Prizes, and Logs.
"""

import os
import sys
import logging
import datetime
from functools import wraps
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify, abort, send_file, redirect, url_for, render_template, session
from flask_babel import Babel 
from werkzeug.security import check_password_hash

# --- DATABASE & MODULE IMPORTS ---
from db_utils import init_db, get_db_connection
import add_student
import student_search
import transaction_manager
import alerts

# ---- 1. Paths and App Setup ----
basedir = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "prod-secret-must-be-set")

# ---- 2. Babel Localization Setup ----
def get_locale():
    if 'lang' in request.args:
        lang = request.args['lang']
        if lang in app.config.get('LANGUAGES', {}):
            return lang
    return request.accept_languages.best_match(['en', 'es'])

app.config['LANGUAGES'] = {'en': 'English', 'es': 'Español'}
babel = Babel(app, locale_selector=get_locale)

# ---- 3. Authentication Decorator ----
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# ---- 4. Logging Setup ----
LOG_PATH = os.path.join(basedir, 'logs', 'app.log')
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

class EmailAlertHandler(logging.Handler):
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            try:
                msg = self.format(record)
                alerts.send_alert(subject=f"System Error: {record.levelname}", message=msg)
            except Exception:
                self.handleError(record)

handler = RotatingFileHandler(LOG_PATH, maxBytes=500000, backupCount=3)
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logging.getLogger().addHandler(handler)
logging.getLogger().addHandler(EmailAlertHandler())
logger = logging.getLogger(__name__)

# ---- 5. Auth Routes ----
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = request.form.get('username'), request.form.get('password')
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
    session.clear()
    return redirect(url_for('login'))

# ---- 6. UI Routes (All Protected) ----
@app.route('/')
@login_required
def index(): return render_template('index.html')

@app.route('/students')
@app.route('/students_list')
@login_required
def students_page(): return render_template('students.html')

@app.route('/student/<int:student_id>')
@login_required
def student_profile(student_id): return render_template('student_profile.html', student_id=student_id)

@app.route('/student_history/<int:student_id>')
@login_required
def student_history_page(student_id): return render_template('student_history.html', student_id=student_id)

@app.route('/add_student')
@login_required
def add_student_page(): return render_template('add_student.html')

@app.route('/activity')
@login_required
def activity_form(): return render_template('add_activity.html')

@app.route('/record_activity')
@login_required
def record_activity_page(): return render_template('record_activity.html')

@app.route('/prizes')
@login_required
def prizes_page(): return render_template('prizes.html')

@app.route('/redeem')
@login_required
def redeem_page(): return render_template('redeem.html')

@app.route('/audit_logs')
@login_required
def audit_logs_page(): return render_template('audit_logs.html')

@app.route('/logs')
@login_required
def logs_page(): return render_template('logs.html')

# ---- 7. Student Management API ----
@app.route('/api/students/search', methods=['GET'])
@login_required
def api_student_search():
    term = request.args.get('term', '')
    if len(term) < 2: return jsonify({"success": True, "students": []})
    return jsonify({"success": True, "students": student_search.find_students(term)})

@app.route('/api/student/<int:student_id>', methods=['GET'])
@login_required
def api_get_student_details(student_id):
    student = student_search.get_student_by_id(student_id)
    return jsonify({"success": True, "student": student}) if student else (jsonify({"success": False}), 404)

@app.route('/api/student/<int:student_id>/history', methods=['GET'])
@login_required
def api_student_history(student_id):
    student = student_search.get_student_by_id(student_id)
    if not student: return jsonify({"success": False, "message": "Student not found"}), 404
    history = transaction_manager.get_student_transactions(student_id)
    balance = transaction_manager.get_student_balance(student_id)
    return jsonify({
        "success": True, 
        "student_name": student['full_name'], 
        "history": history, 
        "total_points": balance
    })

# ---- 8. Activity & Transaction API ----
@app.route('/api/activity', methods=['GET'])
@login_required
def api_list_active_activities():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, default_points FROM activities WHERE active = TRUE ORDER BY name")
    results = cur.fetchall()
    conn.close()
    return jsonify(results)

@app.route('/api/list_activities', methods=['GET'])
@login_required
def api_list_all_activities():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, default_points, active FROM activities ORDER BY name")
    results = cur.fetchall()
    conn.close()
    return jsonify({"activities": results})

@app.route('/api/transaction/record', methods=['POST'])
@login_required
def api_record_transaction():
    data = request.get_json()
    success, msg = transaction_manager.add_points(
        data['student_id'], 
        int(data['points']), 
        data.get('activity_name', 'Manual'), 
        data.get('description', ''), 
        session['username']
    )
    return jsonify({"success": success, "message": msg})

# ---- 9. Prize Management API ----
@app.route('/api/prizes', methods=['GET'])
@login_required
def api_list_prizes():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM prize_inventory ORDER BY name")
    results = cur.fetchall()
    conn.close()
    return jsonify({"prizes": results})

@app.route('/api/prizes/redeem', methods=['POST'])
@login_required
def api_redeem_prize():
    data = request.get_json()
    # Using the transactional logic we confirmed earlier
    success, msg = transaction_manager.add_points(
        student_id=data['student_id'],
        points=-abs(data.get('point_cost', 0)),
        activity_type=f"Redemption: {data.get('prize_name')}",
        description="Prize Exchange",
        recorded_by=session['username']
    )
    return jsonify({"success": success, "message": msg})

# ---- 10. System Logs & Audit API ----
@app.route('/api/logs/view')
@login_required
def api_view_logs():
    if not os.path.exists(LOG_PATH): return jsonify({'logs': ['Log file empty.']})
    with open(LOG_PATH, 'r') as f:
        lines = f.readlines()
        return jsonify({'logs': lines[-100:]})

@app.route('/api/logs/audit')
@login_required
def api_view_audit_logs():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM audit_log ORDER BY event_time DESC LIMIT 100")
    results = cur.fetchall()
    conn.close()
    return jsonify({"success": True, "logs": results})

if __name__ == '__main__':
    # Initialize DB tables if they don't exist
    init_db()
    app.run(debug=True)