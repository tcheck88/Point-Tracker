"""
app.py - Leer México Activity Manager backend (PostgreSQL Version)
Restored Production Version
"""

from dotenv import load_dotenv  
import os
import sys
import logging
import datetime
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify, abort, send_file, redirect, url_for, render_template, send_from_directory, session
from flask_babel import Babel 
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# --- IMPORTS FOR POSTGRESQL ---
from db_utils import init_db, get_db_connection
import add_student
import student_search
import transaction_manager
import alerts 
import threading  

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
            print(f"DEBUG: Language set to {lang} via URL")  # <--- DEBUG
            return lang
            
    # 2. Check Session (persistence)
    if 'lang' in session:           # <--- NEW: Remembers choice on next page load
        print(f"DEBUG: Language loaded from SESSION: {session['lang']}") # <--- DEBUG
        return session['lang']
        
    # 3. Fallback to Browser Headers
    print("DEBUG: Using default browser language")
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
        if session.get('role') != 'admin':
            # Check if it's an API call or a regular page load
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({"success": False, "message": "Access Denied: Admins only."}), 403
            else:
                # Flash a message and redirect to dashboard (or render a 403 page)
                # return render_template('403.html'), 403  <-- If you have a 403.html
                return redirect(url_for('index')) 
        return f(*args, **kwargs)
    return decorated_function    
    

# ---- 4. Logging Setup ----
class EmailAlertHandler(logging.Handler):
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            try:
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
                        # If email fails, just log it to console so we don't crash
                        print(f"Background Email Failed: {e}")

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

# ---- 5. Database Setup ----
try:
    init_db()
    logger.info("Database initialized successfully.")
except Exception as e:
    logger.critical(f"Database initialization failed: {e}")

# ---- ROUTES START BELOW ----

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
            session['role'] = user['role']
            return redirect(url_for('index'))
        
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
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

        # Update the record
        cur.execute("""
            UPDATE students 
            SET full_name = %s,
                nickname = %s,
                grade = %s,
                classroom = %s,
                parent_name = %s,
                phone = %s,
                email = %s,
                sms_consent = %s
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
        logger.error(f"Error updating student {student_id}: {e}")
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
        logger.error(f"Error fetching student {student_id}: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/students/search', methods=['GET'])
@login_required
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


# ---- Transaction API  ----

@app.route('/api/transaction/record', methods=['POST'])
@login_required
def api_record_transaction():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON payload."}), 400

    student_id = data.get('student_id')
    activity_name = data.get('activity_name', 'Manual Entry')
    points = data.get('points')
    
    if not student_id or points is None:
        return jsonify({"success": False, "message": "Missing Student ID or Points value."}), 400

    staff_identity = session.get('username', 'system')

    success, msg = transaction_manager.add_points(
        student_id=student_id,
        points=int(points),
        activity_type=activity_name,
        description=data.get('description', ''),
        recorded_by=staff_identity
    )

    if success:
        logger.info(f"Points recorded for student {student_id} by {staff_identity}")
        return jsonify({"success": True, "message": msg}), 200
    else:
        logger.error(f"Transaction failed for student {student_id}: {msg}")
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
        logger.error(f"History error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


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

    if not name:
        return jsonify({"success": False, "message": "Name is required"}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO activities (name, description, default_points, active)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                description = EXCLUDED.description,
                default_points = EXCLUDED.default_points,
                active = EXCLUDED.active
        """, (name, desc, pts, is_active))
        conn.commit()
        return jsonify({"success": True, "message": "Activity saved"}), 200
    except Exception as e:
        logger.error(f"Error saving activity: {e}")
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
        logger.error(f"Error fetching activities for dropdown: {e}")
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
        logger.error(f"Error listing activities: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/activity/delete/<int:activity_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_activity(activity_id):
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
        app.logger.error(f"Error downloading log: {e}")
        abort(500)

@app.route('/api/logs/clear', methods=['POST'])
@login_required
@admin_required
def clear_logs():
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
        cur.execute("""
            INSERT INTO prize_inventory (name, description, point_cost, stock_count, active)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                point_cost = EXCLUDED.point_cost,
                stock_count = EXCLUDED.stock_count,
                active = EXCLUDED.active,
                description = EXCLUDED.description
        """, (name, data.get('description', ''), cost, stock, active))
        
        transaction_manager.log_audit_event(
            action_type="UPDATE_PRIZE",
            details=f"Updated prize '{name}': Cost={cost}, Stock={stock}, Active={active}",
            recorded_by=staff_identity
        )
        
        conn.commit()
        return jsonify({"success": True, "message": f"Prize '{name}' saved successfully"}), 200
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error saving prize: {e}")
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
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Invalid request."}), 400

    student_id = data.get('student_id')
    prize_id = data.get('prize_id')
    staff_identity = session.get('username', 'system')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database connection error."}), 500

    try:
        cur = conn.cursor()
        cur.execute("SELECT name, point_cost, stock_count FROM prize_inventory WHERE id = %s", (prize_id,))
        prize = cur.fetchone()
        
        if not prize:
            return jsonify({"success": False, "message": "Prize not found."}), 404
        
        is_dict = isinstance(prize, dict)
        p_name = prize['name'] if is_dict else prize[0]
        p_cost = prize['point_cost'] if is_dict else prize[1]
        p_stock = prize['stock_count'] if is_dict else prize[2]

        if p_stock <= 0:
            return jsonify({"success": False, "message": f"'{p_name}' is out of stock."}), 400

        balance = transaction_manager.get_student_balance(student_id)
        if balance < p_cost:
            return jsonify({"success": False, "message": "Student has insufficient points."}), 400

        success, msg = transaction_manager.add_points(
            student_id=student_id, 
            points=-abs(p_cost), 
            activity_type=f"Redemption: {p_name}",
            description="Prize Exchange",
            recorded_by=staff_identity
        )
        
        if success:
            cur.execute("UPDATE prize_inventory SET stock_count = stock_count - 1 WHERE id = %s", (prize_id,))
            conn.commit()
            logger.info(f"Redemption successful: Student {student_id} redeemed {p_name} (recorded by {staff_identity})")
            return jsonify({"success": True, "message": f"Successfully redeemed {p_name}!"}), 200
        else:
            conn.rollback()
            return jsonify({"success": False, "message": msg}), 500
            
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Redemption API Error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/prizes/delete/<int:prize_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_prize(prize_id):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM prize_inventory WHERE id = %s", (prize_id,))
        prz = cur.fetchone()
        if not prz:
            return jsonify({"success": False, "message": "Prize not found"}), 404
        
        prize_name = prz['name'] if isinstance(prz, dict) else prz[0]

        redemption_str = f"Redemption: {prize_name}"
        cur.execute("SELECT COUNT(*) FROM activity_log WHERE activity_type = %s", (redemption_str,))
        count = cur.fetchone()
        log_count = count['count'] if isinstance(count, dict) else count[0]

        if log_count > 0:
            return jsonify({
                "success": False, 
                "message": f"Cannot delete '{prize_name}' because it has {log_count} redemptions. Set it to 'Inactive' instead."
            }), 400

        cur.execute("DELETE FROM prize_inventory WHERE id = %s", (prize_id,))
        conn.commit()
        return jsonify({"success": True, "message": "Prize deleted successfully"}), 200
    finally:
        conn.close()

# ---- Audit Log API ----

@app.route('/api/logs/audit')
@login_required
@admin_required
def api_view_audit_logs_data():
    conn = get_db_connection()
    if not conn: return jsonify({"success": False}), 500
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, action_type, details, recorded_by, event_time 
            FROM audit_log 
            ORDER BY event_time DESC LIMIT 100
        """)
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
