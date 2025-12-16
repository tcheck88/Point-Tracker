import logging
from db_utils import get_db_connection

logger = logging.getLogger(__name__)

# --- 1. The Main "New" Logic ---
def add_points(student_id, points, activity_type, description=""):
    """
    Records a point transaction in Supabase.
    Signature matches the new app.py calls.
    """
    conn = get_db_connection()
    if not conn:
        return False, "Database connection failed."

    try:
        cur = conn.cursor()
        
        # Postgres uses %s
        cur.execute("""
            INSERT INTO activity_log (student_id, activity_type, points, description)
            VALUES (%s, %s, %s, %s)
        """, (student_id, activity_type, points, description))

        conn.commit()
        logger.info(f"Added {points} points for student {student_id} ({activity_type})")
        return True, "Points added successfully."

    except Exception as e:
        conn.rollback()
        logger.error(f"Error adding points: {e}")
        return False, f"Error: {e}"
    finally:
        if conn:
            conn.close()

# --- 2. The Legacy Adapter (Crucial for compatibility) ---
def record_activity_transaction(db_path_ignored, student_id, activity_name, points, performed_by="system"):
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

def get_student_transactions(db_path_ignored, student_id):
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
    Calculates total points for a student.
    """
    conn = get_db_connection()
    if not conn:
        return 0

    try:
        cur = conn.cursor()
        cur.execute("SELECT SUM(points) as total FROM activity_log WHERE student_id = %s", (student_id,))
        result = cur.fetchone()
        
        # Handle None result safely
        if result and result.get('total') is not None:
            return result['total']
        return 0
    except Exception as e:
        logger.error(f"Error calculating balance: {e}")
        return 0
    finally:
        if conn:
            conn.close()