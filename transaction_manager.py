import logging
from db_utils import get_db_connection

logger = logging.getLogger(__name__)

# --- 1. The Main "New" Logic ---
def add_points(student_id, points, activity_type, description="", recorded_by="system"):
    conn = get_db_connection()
    if not conn:
        return False, "Database connection failed."

    try:
        cur = conn.cursor()
        
        # Record the transaction with the new strongly typed column
        cur.execute("""
            INSERT INTO activity_log (student_id, activity_type, points, description, recorded_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (student_id, activity_type, points, description, recorded_by))

        # Update student cache
        cur.execute("""
            UPDATE students 
            SET total_points = COALESCE(total_points, 0) + %s 
            WHERE id = %s
        """, (points, student_id))

        conn.commit()
        return True, "Points added successfully."
    except Exception as e:
        conn.rollback()
        logger.error(f"Error adding points: {e}")
        return False, f"Error: {e}"
    finally:
        conn.close()
        
        

# --- 2. The Legacy Adapter (Crucial for compatibility) ---
def record_activity_transaction(student_id, activity_name, points, performed_by="system"):
    """
    Adapter function to support legacy calls from app.py.
    Maps the 5 old arguments to the 4 new arguments of add_points.
    """
    # We ignore db_path_ignored since we use Supabase now.
    # We combine 'performed_by' into the description.
    description = f"Performed by: {performed_by}"
    
    # Call the actual logic function
    success, message = add_points(student_id, points, activity_name, description)
    
    # Legacy code expects a simple Boolean, not a tuple
    return success

def get_student_transactions(student_id):
    """
    Fetches transaction history for a student.
    Ignores db_path, uses Supabase connection.
    """
    conn = get_db_connection()
    if not conn:
        return []

    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM activity_log 
            WHERE student_id = %s 
            ORDER BY timestamp DESC
        """, (student_id,))
        
        return cur.fetchall()
    except Exception as e:
        logger.error(f"Error fetching transactions: {e}")
        return []
    finally:
        if conn:
            conn.close()
            
def get_student_balance(student_id):
    """
    Fetches the total points directly from the students table cache.
    This is faster than summing history logs for every request.
    """
    conn = get_db_connection()
    if not conn:
        return 0

    try:
        cur = conn.cursor()
        # Read from the cached column instead of SUM(activity_log)
        cur.execute("SELECT total_points FROM students WHERE id = %s", (student_id,))
        result = cur.fetchone()
        
        # Handle dict or tuple results for PostgreSQL compatibility
        if result:
            is_dict = isinstance(result, dict)
            points = result['total_points'] if is_dict else result[0]
            return points if points is not None else 0
        return 0
    except Exception as e:
        logger.error(f"Error reading balance cache: {e}")
        return 0
    finally:
        if conn:
            conn.close()
            
       

def log_audit_event(action_type, details, recorded_by="system"):
    """
    Records a system-level audit event (e.g., Prize Edit, Student Added).
    """
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()
        # FIX: Changed column 'timestamp' to 'event_time'
        cur.execute("""
            INSERT INTO audit_log (action_type, details, recorded_by, event_time)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
        """, (action_type, details, recorded_by))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Audit log failure: {e}")
        return False
    finally:
        conn.close()


