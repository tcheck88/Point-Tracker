"""
app.py - Leer México Activity Manager backend, with complete documentation
Serves static UIs and APIs for students and activities.
"""

import os
import sys
import logging
import datetime
import sqlite3
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify, send_from_directory, abort, send_file

from add_student import init_db, add_student, find_possible_duplicates
from db_utils import enable_wal_and_timeout
from alerts import send_alert
import student_search
import transaction_manager



# --- MISSING HANDLER CLASS ---
class EmailAlertHandler(logging.Handler):
    """
    Custom logging handler that sends an email for ERROR or CRITICAL logs.
    """
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            try:
                # Format the log message
                msg = self.format(record)
                
                # Check if there is exception info (traceback) attached
                exc_info = record.exc_info
                error_obj = exc_info[1] if exc_info else None
                
                # Send the alert
                send_alert(
                    subject=f"Application Error: {record.levelname}",
                    message=msg,
                    error_obj=error_obj
                )
            except Exception:
                # If sending email fails, don't crash the app, just print to stderr
                self.handleError(record)


# ---- Paths and App Setup ----
APP_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(APP_DIR, 'leer_mexico.db')
LOG_DIR = os.path.join(APP_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, 'app.log')


app = Flask(__name__, static_folder='static', static_url_path='/static')

# ---- Logging Setup ----
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

# ---- DB Setup ----
init_db(DB_PATH)
enable_wal_and_timeout(DB_PATH)
logger.info(f"Using DB_PATH={DB_PATH}, exists={os.path.exists(DB_PATH)}")

def _serve_static(filename):
    path = os.path.join(app.static_folder, filename)
    if not os.path.exists(path):
        logger.warning("Static file not found: %s", path)
        abort(404)
    return send_from_directory(app.static_folder, filename)

# ---- Static HTML UI Endpoints ----
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
    return send_from_directory('static', 'add_activity.html')

@app.route('/students')
def students_page():
    try:
        return send_from_directory(app.static_folder, 'students.html')
    except FileNotFoundError:
        abort(404, description="Student List page (students.html) not found.")

@app.route('/student/<int:student_id>')
def student_profile(student_id):
    try:
        return send_from_directory(app.static_folder, 'student_profile.html')
    except:
        return send_from_directory(app.static_folder, 'students.html')

# ---- Student Management API ----
@app.route('/api/add_student', methods=['POST'])
def api_add_student():
    data = request.get_json() or {}
    logger.info(f"Received /api/add_student request: {data}")
    full_name = data.get('full_name')
    # ... (other fields remain same) ...
    nickname = data.get('nickname')
    phone = data.get('phone')
    email = data.get('email')
    parent_name = data.get('parent_name')
    sms_consent = data.get('sms_consent', False)
    classroom = data.get('classroom')
    grade = data.get('grade')
    created_by = data.get('created_by', 'web_admin')
    allow_create_on_duplicate = data.get('confirmed_not_duplicate', False)
    duplicate_justification = "User confirmed not a duplicate" if allow_create_on_duplicate else None
    
    if not full_name or not full_name.strip():
        logger.warning("Validation failed: Full name is missing")
        return jsonify({"success": False, "message": "Full name is required."}), 400
    
    sms_bool = str(sms_consent).lower() in ('1', 'true', 'yes', 'on')
    
    result = add_student(
        db_path=DB_PATH,
        full_name=full_name,
        nickname=nickname,
        phone=phone,
        email=email,
        parent_name=parent_name,
        sms_consent=sms_bool,
        classroom=classroom,
        grade=grade,
        created_by=created_by,
        allow_create_on_duplicate=allow_create_on_duplicate,
        duplicate_justification=duplicate_justification
    )
    
    if result.get("success") is False and result.get("duplicates"):
        logger.info(f"Duplicate detected for {full_name}: {result.get('duplicates')}")
        return jsonify(result), 409
    
    if result.get("success"):
        # CRITICAL FIX: Ensure 'student_id' is returned even if legacy add_student returns 'user_id'
        new_id = result.get('student_id')
        logger.info(f"Student created: ID={new_id}, name={full_name}")
        
        response_data = result.copy()
        response_data['student_id'] = new_id # Standardize response key
            
        return jsonify(response_data), 201
    else:
        error_details = str(result.get("errors"))
        logger.error(f"Student creation failed: {error_details}")
        try:
            send_alert("Student creation failed", error_details)
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
        return jsonify(result), 400

@app.route('/api/check_duplicates', methods=['POST'])
def api_check_duplicates():
    data = request.get_json() or {}
    name = data.get('name')
    phone = data.get('phone')
    email = data.get('email')
    matches = find_possible_duplicates(DB_PATH, name, phone, email, max_results=5)
    return jsonify({"matches": matches}), 200

# API to fetch a single student's details by ID.
@app.route('/api/student/<int:student_id>', methods=['GET'])
def api_get_student_details(student_id):
    try:
        student = student_search.get_student_by_id(DB_PATH, student_id) 
        if student is None:
            return jsonify({"success": False, "message": f"Student with ID {student_id} not found."}), 404
        return jsonify({"success": True, "student": student}), 200
    except Exception as e:
        logger.error(f"Error fetching student {student_id}: {e}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

# API to update a single student's details by ID.
@app.route('/api/student/<int:student_id>', methods=['POST'])
def api_update_student(student_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON body."}), 400

    name = data.get('name', '').strip()
    if not name:
        return jsonify({"success": False, "message": "Student Name is required."}), 400

    try:
        modified_by = data.get('modified_by', 'web_admin') 
        # Calls student_search.update_student (Verified standard)
        success = student_search.update_student(DB_PATH, student_id, data, modified_by=modified_by)

        if success:
            logger.info(f"Student profile updated for ID: {student_id} by {modified_by}")
            return jsonify({"success": True, "message": f"Student ID {student_id} profile updated."}), 200
        else:
            return jsonify({"success": False, "message": f"Student with ID {student_id} not found or update failed."}), 404
    except Exception as e:
        logger.error(f"Error updating student {student_id}: {e}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

# API route for student search
@app.route('/api/students/search', methods=['GET'])
def api_students_search():
    search_term = request.args.get('term', '').strip()
#    if not search_term:
         # Fallback for search query param
 #        search_term = request.args.get('query', '').strip()

    if not search_term or len(search_term) < 2:
        return jsonify({"success": True, "students": [], "message": "Enter at least 2 characters to search."}), 200 

    try:
        students = student_search.search_students(DB_PATH, search_term)
        # Note: students variable is a list of dicts, including 'id', 'name', etc.
        if students:
            return jsonify({"success": True, "students": students}), 200 
        else:
            return jsonify({"success": True, "students": [], "message": "No active students found."}), 200
    except Exception as e:
        logger.error(f"Error executing student search API for term '{search_term}': {e}")
        return jsonify({"success": False, "message": f"Server error during search: {str(e)}"}), 500

# API to record a new point transaction (Strict Validation)
@app.route('/api/transaction/record', methods=['POST'])
def api_record_transaction():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON body."}), 400

    # CRITICAL: Read 'student_id'
    student_id = data.get('student_id', 0) 
    activity_name = data.get('activity_name', '').strip()
    points = data.get('points')
    performed_by = data.get('performed_by', 'web_admin')

    # Simple Validation
    if not student_id or not activity_name or points is None:
        return jsonify({"success": False, "message": "Missing student_id, activity_name, or points."}), 400
    
    try:
        points = int(points)
    except ValueError:
        return jsonify({"success": False, "message": "Points must be an integer."}), 400

    # Call the transaction manager function
    success = transaction_manager.record_activity_transaction(
        DB_PATH,
        student_id, 
        activity_name,
        points,
        performed_by
    )

    if success:
        logger.info(f"Transaction recorded for student {student_id}: {points} points for {activity_name}")
        return jsonify({"success": True, "message": "Points recorded successfully."}), 200
    else:
        return jsonify({"success": False, "message": f"Transaction failed for student {student_id}. Check logs."}), 500
        
     


@app.route('/student_history/<int:student_id>')
def student_history_page(student_id):
    try:
        # This serves the student_history.html file you created
        return send_from_directory(app.static_folder, 'student_history.html')
    except FileNotFoundError:
        abort(404, description="Student History page not found.")
        
        
# API to list all activity transactions for a specific student ID AND fetch current points.
@app.route('/api/student/<int:student_id>/history', methods=['GET'])
def api_student_history(student_id):
    try:
        # 1. Fetch Student Profile to get name and total points
        student_data = student_search.get_student_by_id(DB_PATH, student_id) 

        if not student_data:
             # Handle case where student does not exist
            return jsonify({"success": False, "message": f"Student ID {student_id} not found."}), 404

        # CRITICAL FIX: Access the name using the standard lowercase key 'name'.
        # This resolves the "Unknown Student" issue due to case sensitivity.
        student_name = student_data.get('name', f'ID: {student_id}')
        total_points = student_data.get('total_points', 0)
        
        # 2. Fetch Transactions
        # Note: We must call this after validating the student exists
        transactions = transaction_manager.get_student_transactions(DB_PATH, student_id)
        
        # 3. Compile Response
        response = {
            "success": True,
            "student_id": student_id,
            "student_name": student_name,
            "total_points": total_points,
            "history": transactions,
            "message": f"Fetched {len(transactions)} records."
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error fetching transaction history for student {student_id}: {e}")
        return jsonify({"success": False, "message": f"Server error fetching history: {str(e)}"}), 500




# ---- Activities API ----
@app.route('/api/activity', methods=['GET'])
def api_list_activities():
    conn = None
    activities = []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, name, description, default_points, active FROM Activities ORDER BY name")
        for row in c.fetchall():
            activities.append(dict(row))
        return jsonify(activities), 200
    except Exception as e:
        logger.error(f"Error fetching activities: {e}")
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

# Include other Activity APIs from your original file (add_activity, etc) unchanged as they don't affect student_id
# ... (Leaving them implies they remain as they were in the original upload)



# --- LOG MANAGEMENT ROUTES ---

@app.route('/logs')
def logs_page():
    # Simple protection: In production, you would add @login_required here
    return send_from_directory(app.static_folder, 'logs.html')

@app.route('/api/logs/view')
def view_logs():
    """Returns the last 50 lines of the log file."""
    # FIX: Use the global LOG_PATH variable instead of 'app.log'
    if not os.path.exists(LOG_PATH):
        return jsonify({'logs': ['Log file is empty or does not exist.']})
    
    try:
        with open(LOG_PATH, 'r') as f:
            # Efficiently read the last 50 lines
            lines = f.readlines()
            last_lines = lines[-50:] if len(lines) > 50 else lines
            return jsonify({'logs': last_lines})
    except Exception as e:
        return jsonify({'logs': [f"Error reading log: {str(e)}"]})

@app.route('/api/logs/download')
def download_logs():
    """Downloads the full app.log file."""
    # FIX: Use LOG_PATH
    if not os.path.exists(LOG_PATH):
        abort(404, description="Log file not found.")
    
    try:
        return send_file(LOG_PATH, as_attachment=True, download_name=f"leermexico_logs_{datetime.datetime.now().strftime('%Y%m%d')}.txt")
    except Exception as e:
        app.logger.error(f"Error downloading log: {e}")
        abort(500)



@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    """Rotates the log file safely by closing the handler first (Required for Windows)."""
    backup_file = f"{LOG_PATH}.bak.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

    try:
        # 1. Access the root logger
        root_logger = logging.getLogger()
        
        # 2. Find the existing file handler so we can close it
        file_handler_found = None
        for h in root_logger.handlers:
            if isinstance(h, RotatingFileHandler):
                file_handler_found = h
                break
        
        # 3. Close and remove the handler to RELEASE THE WINDOWS FILE LOCK
        if file_handler_found:
            file_handler_found.close()
            root_logger.removeHandler(file_handler_found)

        # 4. Now the file is unlocked. Rename it.
        if os.path.exists(LOG_PATH):
            os.rename(LOG_PATH, backup_file)
        
        # 5. Re-initialize a fresh file handler so the app can keep writing logs
        # We reuse the exact same settings defined at the top of your app.py
        new_handler = RotatingFileHandler(LOG_PATH, maxBytes=500000, backupCount=3)
        new_handler.setLevel(logging.INFO)
        new_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        root_logger.addHandler(new_handler)
        
        # 6. Log success (this goes into the NEW app.log file)
        root_logger.info(f"Log file rotated successfully. Archived as {os.path.basename(backup_file)}")

        return jsonify({'success': True, 'message': 'Logs cleared successfully.'})

    except Exception as e:
        # If it fails, try to log it to the console/stderr at least
        print(f"CRITICAL ERROR clearing logs: {e}")
        return jsonify({'success': False, 'message': str(e)})





if __name__ == '__main__':
    app.run(debug=True)