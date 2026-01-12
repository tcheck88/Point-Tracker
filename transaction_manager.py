import logging
from db_utils import get_db_connection
import alerts  

logger = logging.getLogger(__name__)

# --- 1. The Main "New" Logic ---

def add_points(student_id, points, activity_type, description="", recorded_by="system", activity_id=None, prize_id=None, audit_action="POINT_AWARD"):
    conn = get_db_connection()
    if not conn:
        return False, "Database connection failed."

    try:
        cur = conn.cursor()
        
        # 1. Fetch Student Name
        s_name = "Unknown"
        try:
            cur.execute("SELECT full_name FROM students WHERE id = %s", (student_id,))
            res = cur.fetchone()
            if res:
                s_name = res['full_name'] if isinstance(res, dict) else res[0]
        except Exception:
            pass 

        # 2. Record Transaction
        cur.execute("""
            INSERT INTO activity_log 
            (student_id, activity_type, points, description, recorded_by, activity_id, prize_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (student_id, activity_type, points, description, recorded_by, activity_id, prize_id))
        
        new_trans_id = cur.fetchone()['id']

        # 3. Update Balance
        cur.execute("""
            UPDATE students 
            SET total_points = COALESCE(total_points, 0) + %s 
            WHERE id = %s
        """, (points, student_id))

        # 4. AUDIT LOG (Uses the new audit_action parameter)
        audit_details = f"Points: {points}, Student: {s_name} (ID: {student_id}), Type: {activity_type}"
        
        cur.execute("""
            INSERT INTO audit_log 
            (event_time, event_type, action_type, actor, recorded_by, target_table, target_id, details)
            VALUES (CURRENT_TIMESTAMP, 'TRANSACTION', %s, %s, %s, 'activity_log', %s, %s)
        """, (audit_action, recorded_by, recorded_by, new_trans_id, audit_details))

        # 5. ALERTS
        if points > 0:
            threshold = 500
            try:
                cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = 'POINT_ALERT_THRESHOLD'")
                row = cur.fetchone()
                if row:
                    val = row['setting_value'] if isinstance(row, dict) else row[0]
                    threshold = int(val)
            except Exception:
                pass 

            if points >= threshold:
                alerts.send_alert(
                    subject=f"High Point Alert: {points} pts",
                    message=f"Student <b>{s_name}</b> was awarded <b>{points} points</b>.<br>Reason: {activity_type}<br>Staff: {recorded_by}"
                )

        conn.commit()
        logger.info(f"Transaction Success: {points} pts for {s_name} (ID: {student_id})")
        return True, "Points saved successfully."

    except Exception as e:
        conn.rollback()
        logger.exception(f"Error adding points: {e}")
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
        logger.exception(f"Error fetching transactions: {e}")
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
        logger.exception(f"Error reading balance cache: {e}")
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
        logger.exception(f"Audit log failure: {e}")
        return False
    finally:
        conn.close()


def redeem_prize_logic(student_id, prize_id, recorded_by):
    conn = get_db_connection()
    if not conn:
        return False, "Could not connect to database."

    try:
        cur = conn.cursor()
        
        # 1. Fetch Prize
        cur.execute("SELECT name, point_cost, stock_count FROM prize_inventory WHERE id = %s", (prize_id,))
        prize = cur.fetchone()
        if not prize: return False, "Prize not found."

        p_name = prize['name'] if isinstance(prize, dict) else prize[0]
        p_cost = prize['point_cost'] if isinstance(prize, dict) else prize[1]
        p_stock = prize['stock_count'] if isinstance(prize, dict) else prize[2]

        if p_stock <= 0: return False, f"'{p_name}' is out of stock."

        current_balance = get_student_balance(student_id)
        if current_balance < p_cost: return False, "Insufficient points."

        # 2. Process Transaction with OVERRIDE for Audit Action
        success, msg = add_points(
            student_id=student_id,
            points=-abs(p_cost),
            activity_type=f"Redemption: {p_name}",
            description="Prize Exchange",
            recorded_by=recorded_by,
            prize_id=prize_id,
            audit_action="REDEEM_POINTS"  # <--- CHANGED THIS
        )

        if success:
            # 3. Update Inventory
            cur.execute("UPDATE prize_inventory SET stock_count = stock_count - 1 WHERE id = %s", (prize_id,))
            
            # Fetch student name
            s_name = "Unknown"
            try:
                cur.execute("SELECT full_name FROM students WHERE id = %s", (student_id,))
                res = cur.fetchone()
                if res: s_name = res['full_name'] if isinstance(res, dict) else res[0]
            except: pass

            # 4. AUDIT LOG (Action: PRIZE_REDEEM)
            # This logs the physical stock change
            audit_details = f"Redeemed: {p_name}, By: {s_name} (ID: {student_id})"
            
            cur.execute("""
                INSERT INTO audit_log 
                (event_time, event_type, action_type, actor, recorded_by, target_table, target_id, details)
                VALUES (CURRENT_TIMESTAMP, 'INVENTORY', 'PRIZE_REDEEM', %s, %s, 'prize_inventory', %s, %s)
            """, (recorded_by, recorded_by, prize_id, audit_details))

            conn.commit()
            logger.info(f"Redemption Success: {s_name} redeemed '{p_name}'")
            return True, f"Successfully redeemed {p_name}!"

        return False, msg

    except Exception as e:
        conn.rollback()
        alerts.send_alert("Redemption Crash", f"Error during prize redemption for student {student_id}: {e}")
        logger.exception(f"Redemption error: {e}")
        return False, f"Internal Error: {e}"
    finally:
        conn.close()

def redeem_prize_logic(student_id, prize_id, recorded_by):
    conn = get_db_connection()
    if not conn:
        return False, "Could not connect to database."

    try:
        cur = conn.cursor()
        
        # 1. Fetch Prize
        cur.execute("SELECT name, point_cost, stock_count FROM prize_inventory WHERE id = %s", (prize_id,))
        prize = cur.fetchone()
        if not prize: return False, "Prize not found."

        p_name = prize['name'] if isinstance(prize, dict) else prize[0]
        p_cost = prize['point_cost'] if isinstance(prize, dict) else prize[1]
        p_stock = prize['stock_count'] if isinstance(prize, dict) else prize[2]

        if p_stock <= 0: return False, f"'{p_name}' is out of stock."

        current_balance = get_student_balance(student_id)
        if current_balance < p_cost: return False, "Insufficient points."

        # 2. Process Transaction with OVERRIDE for Audit Action
        success, msg = add_points(
            student_id=student_id,
            points=-abs(p_cost),
            activity_type=f"Redemption: {p_name}",
            description="Prize Exchange",
            recorded_by=recorded_by,
            prize_id=prize_id,
            audit_action="PRIZE_REDEEM"  # <--- OVERRIDE HERE
        )

        if success:
            # 3. Update Inventory
            cur.execute("UPDATE prize_inventory SET stock_count = stock_count - 1 WHERE id = %s", (prize_id,))
            
            # Fetch student name
            s_name = "Unknown"
            try:
                cur.execute("SELECT full_name FROM students WHERE id = %s", (student_id,))
                res = cur.fetchone()
                if res: s_name = res['full_name'] if isinstance(res, dict) else res[0]
            except: pass

            # 4. AUDIT LOG (Action: PRIZE_REDEEM)
            audit_details = f"Redeemed: {p_name}, By: {s_name} (ID: {student_id})"
            
            cur.execute("""
                INSERT INTO audit_log 
                (event_time, event_type, action_type, actor, recorded_by, target_table, target_id, details)
                VALUES (CURRENT_TIMESTAMP, 'INVENTORY', 'PRIZE_REDEEM', %s, %s, 'prize_inventory', %s, %s)
            """, (recorded_by, recorded_by, prize_id, audit_details))

            conn.commit()
            logger.info(f"Redemption Success: {s_name} redeemed '{p_name}'")
            return True, f"Successfully redeemed {p_name}!"

        return False, msg

    except Exception as e:
        conn.rollback()
        alerts.send_alert("Redemption Crash", f"Error during prize redemption for student {student_id}: {e}")
        logger.exception(f"Redemption error: {e}")
        return False, f"Internal Error: {e}"
    finally:
        conn.close()
