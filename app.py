"""
app.py - Leer México Activity Manager backend (PostgreSQL Version)
Serves static UIs and APIs for students and activities.
"""

import os
import sys
import logging
import datetime
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify, send_from_directory, abort, send_file, redirect, url_for

# --- IMPORTS FOR POSTGRESQL ---
from db_utils import init_db, get_db_connection
import add_student
import student_search
import transaction_manager
import alerts 

# --- MISSING HANDLER CLASS (RESTORED) ---
class EmailAlertHandler(logging.Handler):
    """
    Custom logging handler that sends an email for ERROR or CRITICAL logs.
    """
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            try:
                msg = self.format(record)
                exc_info = record.exc_info
                error_obj = exc_info[1] if exc_info else None
                alerts.send_alert(
                    subject=f"Application Error: {record.levelname}",
                    message=msg
                )
            except Exception:
                self.handleError(record)

# ---- Paths and App Setup ----
APP_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(APP_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, 'app.log')

app = Flask(__name__, static_folder='Static', static_url_path='/static')

# ---- Logging Setup (RESTORED) ----
file_handler = RotatingFileHandler(LOG_PATH, maxBytes=500000, backupCount=3)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

console_handler = StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# Remove existing handlers to avoid duplicates during reload
for h in list(root_logger.handlers):
    root_logger.removeHandler(h)

root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

email_handler = EmailAlertHandler()
email_handler.setLevel(logging.ERROR)
email_handler.setFormatter(logging.Formatter('%(message)s'))
root_logger.addHandler(email_handler)

logger = logging.getLogger(__name__)

# ---- DB Setup (UPDATED FOR POSTGRES) ----
# We no longer pass DB_PATH. init_db() uses the Environment Variable.
try:
    init_db()
    logger.info("✅ Database initialized successfully (PostgreSQL).")
except Exception as e:
    logger.critical(f"❌ Database initialization failed: {e}")

def _serve_static(filename):
    path = os.path.join(app.static_folder, filename)
    if not os.path.exists(path):
        logger.warning("Static file not found: %s", path)
        abort(404)
    return send_from_directory(app.static_folder, filename)

# ---- Static HTML UI Endpoints (RESTORED) ----
@app.route('/')
def index():
    return _serve_static('index.html')

@app.route('/add_student')
def add_student_page():
    return _serve_static('add_student.html')

@app.route('/record_activity')
def record_activity_page():
    return _serve_static('record_activity.html')

@app.route('/activity')
def activity_form():
    return _serve_static('add_activity.html')

@app.route('/students')
def students_page():
    return _serve_static('students.html')

@app.route('/student/<int:student_id>')
def student_profile(student_id):
    # Serve the profile page; the JS will fetch data via API
    return _serve_static('student_profile.html')

@app.route('/student_history/<int:student_id>')
def student_history_page(student_id):
    return _serve_static('student_history.html')

@app.route('/logs')
def logs_page():
    return _serve_static('logs.html')


# ---- Student Management API (UPDATED FOR POSTGRES) ----

@app.route('/api/add_student', methods=['POST'])
def api_add_student():
    data = request.get_json() or {}
    logger.info(f"Received /api/add_student request: {data}")
    
    # 1. Prepare Data Dictionary for the new add_student.py
    student_data = {
        'full_name': data.get('full_name'),
        'nickname': data.get('nickname'),
        'phone': data.get('phone'),
        'email': data.get('email'),
        'parent_name': data.get('parent_name'),
        'classroom': data.get('classroom'),
        'grade': data.get('grade'),
        # Convert checkbox/string boolean to Python Boolean
        'sms_consent': str(data.get('sms_consent', '')).lower() in ('1', 'true', 'yes', 'on')
    }
    
    if not student_data['full_name']:
        return jsonify({"success": False, "message": "Full name is required."}), 400
    
    # 2. Call the Postgres-compatible function
    success, message = add_student.add_new_student(student_data)
    
    if success:
        logger.info(f"Student created: {student_data['full_name']}")
        # Note: Phase 2 currently returns simple success. 
        # If you need the new ID immediately, we'd update add_student.py to return it.
        return jsonify({"success": True, "message": message}), 201
    else:
        logger.error(f"Student creation failed: {message}")
        return jsonify({"success": False, "message": message, "errors": message}), 400


@app.route('/api/check_duplicates', methods=['POST'])
def api_check_duplicates():
    # Phase 2: We will rely on simple search for now as duplicates 
    # are harder to fuzzy-match in SQL without extensions.
    # We will implement a basic exact match check here.
    data = request.get_json() or {}
    name = data.get('name', '')
    
    results = student_search.find_students(name)
    # Filter to exact-ish matches
    matches = [s for s in results if name.lower() in s['full_name'].lower()]
    
    return jsonify({"matches": matches}), 200


@app.route('/api/student/<int:student_id>', methods=['GET'])
def api_get_student_details(student_id):
    try:
        student = student_search.get_student_by_id(student_id) 
        if student is None:
            return jsonify({"success": False, "message": f"Student {student_id} not found."}), 404
        return jsonify({"success": True, "student": student}), 200
    except Exception as e:
        logger.error(f"Error fetching student {student_id}: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/students/search', methods=['GET'])
def api_students_search():
    search_term = request.args.get('term', '').strip()
    
    if len(search_term) < 2:
        return jsonify({"success": True, "students": []}), 200 

    try:
        students = student_search.find_students(search_term)
        return jsonify({"success": True, "students": students}), 200 
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ---- Transaction API (UPDATED FOR POSTGRES) ----

@app.route('/api/transaction/record', methods=['POST'])
def api_record_transaction():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON."}), 400

    student_id = data.get('student_id')
    activity_name = data.get('activity_name', 'Manual Entry')
    points = data.get('points')
    
    if not student_id or points is None:
        return jsonify({"success": False, "message": "Missing ID or Points"}), 400

    # Call the new transaction manager
    success, msg = transaction_manager.add_points(student_id, int(points), activity_name)

    if success:
        return jsonify({"success": True, "message": msg}), 200
    else:
        return jsonify({"success": False, "message": msg}), 500


@app.route('/api/student/<int:student_id>/history', methods=['GET'])
def api_student_history(student_id):
    try:
        # 1. Get Student Info
        student = student_search.get_student_by_id(student_id)
        if not student:
            return jsonify({"success": False, "message": "Student not found"}), 404

        # 2. Get Transactions
        history = transaction_manager.get_student_transactions(student_id)
        
        # 3. Get Balance
        total = transaction_manager.get_student_balance(student_id)

        response = {
            "success": True,
            "student_id": student_id,
            "student_name": student['full_name'],
            "total_points": total,
            "history": history
        }
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"History error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ---- Activities List (UPDATED FOR POSTGRES) ----
@app.route('/api/activity', methods=['GET'])
def api_list_activities():
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "DB Connection Error"}), 500
    
    activities = []
    try:
        # Postgres uses a slightly different cursor approach
        cur = conn.cursor()
        cur.execute("SELECT id, name, description, default_points, active FROM activities ORDER BY name")
        activities = cur.fetchall() # RealDictCursor returns list of dicts
        return jsonify(activities), 200
    except Exception as e:
        logger.error(f"Error fetching activities: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


# ---- Log Management (RESTORED EXACTLY) ----
@app.route('/api/logs/view')
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
def download_logs():
    if not os.path.exists(LOG_PATH):
        abort(404, description="Log file not found.")
    try:
        return send_file(LOG_PATH, as_attachment=True, download_name=f"leermexico_logs.txt")
    except Exception as e:
        app.logger.error(f"Error downloading log: {e}")
        abort(500)

@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    """Rotates the log file safely (Windows Compatible)."""
    backup_file = f"{LOG_PATH}.bak.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    try:
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

if __name__ == '__main__':
    logger.info("Starting Point Tracker Application (PostgreSQL)...")
    app.run(debug=True, port=5000)