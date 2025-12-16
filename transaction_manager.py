# transaction_manager.py
import sqlite3
import datetime
import logging
from typing import Dict, Any, Optional, List

# Initialize logger for this module
logger = logging.getLogger(__name__)

ISO_NOW = lambda: datetime.datetime.utcnow().isoformat() + 'Z'
DEFAULT_ACTOR = 'web_admin'

# Helper function (adjusted to use logging)
def write_audit(conn: sqlite3.Connection, event_type: str, actor: str, target_table: str, target_id: Optional[int], details: str) -> None:
    """Writes an entry to the Audit_log table using an existing connection."""
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO Audit_log (event_time, event_type, actor, target_table, target_id, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            ISO_NOW(),
            event_type,
            actor,
            target_table,
            target_id,
            details
        ))
    except Exception as e:
        logger.error(f"ERROR: Failed to write audit log in transaction: {e}")
        raise
        
        

def get_student_transactions(db_path: str, student_id: int) -> List[Dict[str, Any]]:
    """
    Fetches all transaction records for a given student ID.
    Auto-detects schema variations and ensures data is returned even if activity links are broken.
    """
    conn = None
    transactions = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # 1. Inspect Table Columns to determine the correct date field
        c.execute("PRAGMA table_info(Transactions)")
        columns = [row['name'] for row in c.fetchall()]
        
        # Determine which date column to use
        date_col = 'created_at' if 'created_at' in columns else 'date'
        
        # 2. Build Query with LEFT JOIN and dynamic date column
        # LEFT JOIN ensures we get the transaction even if the Activity ID doesn't match a current activity.
        query = f"""
        SELECT
            T.id, 
            T.student_id, 
            T.points_total AS points, 
            T.{date_col} AS date,
            T.created_by AS performed_by, 
            COALESCE(A.name, 'Unknown Activity') AS activity
        FROM Transactions T
        LEFT JOIN Activities A ON T.activity_id = A.id
        WHERE T.student_id = ?
        ORDER BY T.{date_col} DESC
        """
        
        c.execute(query, (student_id,))
        
        transactions = [dict(row) for row in c.fetchall()]
        
        logger.info(f"Fetched {len(transactions)} transactions for student ID {student_id} using column '{date_col}'.")
        
        return transactions

    except Exception as e:
        logger.error(f"Database error fetching transactions for student {student_id}: {e}")
        return []
    finally:
        if conn:
            conn.close()

# Function signature uses student_id
def record_activity_transaction(db_path: str, student_id: int, activity_name: str, points: int, performed_by: str = DEFAULT_ACTOR) -> bool:
    """Records a point transaction and updates the student's total points."""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.isolation_level = 'DEFERRED'
        c = conn.cursor()

        # 1. Check if the student exists
        # CRITICAL FIX 1: Changed table name from 'Users' to 'Students'
        c.execute("SELECT id FROM Students WHERE id = ?", (student_id,))
        if c.fetchone() is None:
            logger.warning(f"Transaction failed: Student ID {student_id} not found.") 
            return False 
        
        # 2. Look up the Activity ID
        c.execute("SELECT id FROM Activities WHERE name = ? AND active = 1", (activity_name,))
        activity_row = c.fetchone()
        if activity_row is None:
            logger.warning(f"Transaction failed: Active activity '{activity_name}' not found.")
            return False
            
        activity_id = activity_row[0]

        # 3. Prepare transaction variables
        points_total = points
        quantity = 1

        # 4. Insert into the Transactions table
        c.execute("""
            INSERT INTO Transactions (
                student_id, activity_id, quantity, points_total, created_by, created_at, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            student_id,
            activity_id,      
            quantity,         
            points_total,     
            performed_by,     
            ISO_NOW(),        
            f"Record activity: {activity_name}"
        ))
        transaction_id = c.lastrowid

        # 5. Update the Students table (total_points) 
        # CRITICAL FIX 2: Changed table name from 'Users' to 'Students'
        c.execute("""
            UPDATE Students
            SET total_points = total_points + ?,
                modified_at = ?,
                modified_by = ?
            WHERE id = ?
        """, (
            points_total,
            ISO_NOW(),
            performed_by,
            student_id
        ))

        # 6. Write to Audit Log
        # CRITICAL FIX 3: Changed target_table from "Users" to "Students"
        write_audit(
            conn,
            event_type="point_transaction",
            actor=performed_by,
            target_table="Students", 
            target_id=student_id,
            details=f"Points updated: {points_total} awarded for activity '{activity_name}'. Transaction ID: {transaction_id}"
        )

        # 7. Commit the entire transaction
        conn.commit()
        return True

    except Exception as e:
        logger.error(f"Transaction failed for student {student_id}: {e}")
        if conn:
            conn.rollback() 
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    pass
    
    
# Note: Remember to ensure this module also has the correct table DDL for Transactions
# which should be consistent with the latest changes:
# 'id', 'student_id', 'date', 'activity', 'points', 'performed_by' (columns assumed based on query)