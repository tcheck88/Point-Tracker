import logging
from db_utils import get_db_connection
import alerts  

logger = logging.getLogger(__name__)

# --- 1. The Main "New" Logic ---
def add_points(student_id, points, activity_type, description="", recorded_by="system"):
    conn = get_db_connection()
    if not conn:
        return False, "Database connection failed."

    try:
        cur = conn.cursor()
        
        # Record the transaction
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
        
        # --- NEW SYSTEM LOGGING ---
        logger.info(f"Transaction Success: {points} pts for Student {student_id} ({activity_type})")
        
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


def redeem_prize_logic(student_id, prize_id, recorded_by):
    """
    Handles the full prize redemption flow:
    Checks stock, verifies points, and records the deduction.
    """
    conn = get_db_connection()
    if not conn:
        return False, "Could not connect to database."

    try:
        cur = conn.cursor()
        
        # 1. Fetch prize info
        cur.execute("SELECT name, point_cost, stock_count FROM prize_inventory WHERE id = %s", (prize_id,))
        prize = cur.fetchone()
        if not prize:
            return False, "Prize not found."

        # Handle both dict and tuple returns
        p_name = prize['name'] if isinstance(prize, dict) else prize[0]
        p_cost = prize['point_cost'] if isinstance(prize, dict) else prize[1]
        p_stock = prize['stock_count'] if isinstance(prize, dict) else prize[2]

        # 2. Safety Checks
        if p_stock <= 0:
            return False, f"'{p_name}' is out of stock."

        current_balance = get_student_balance(student_id)
        if current_balance < p_cost:
            return False, "Insufficient points."

        # 3. Process Transaction (Negative points for redemption)
        success, msg = add_points(
            student_id=student_id,
            points=-abs(p_cost),
            activity_type=f"Redemption: {p_name}",
            description="Prize Exchange",
            recorded_by=recorded_by
        )

        if success:
            # 4. Decrease stock count
            cur.execute("UPDATE prize_inventory SET stock_count = stock_count - 1 WHERE id = %s", (prize_id,))
            conn.commit()
            
            # --- NEW SYSTEM LOGGING ---
            logger.info(f"Redemption Success: Student {student_id} redeemed '{p_name}'")
            
            return True, f"Successfully redeemed {p_name}!"

        return False, msg

    except Exception as e:
        conn.rollback()
        # Trigger an email alert if a database error happens during a money-related transaction
        alerts.send_alert("Redemption Crash", f"Error during prize redemption for student {student_id}: {e}")
        return False, f"Internal Error: {e}"
    finally:
        conn.close()
