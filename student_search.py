import datetime
import logging
from typing import List, Dict, Any, Optional
from db_utils import get_db_connection

logger = logging.getLogger(__name__)

ISO_NOW = lambda: datetime.datetime.utcnow().isoformat() + 'Z'



def write_audit(event_type: str, actor: str, target_table: str, target_id: Optional[int], details: str) -> None:
    conn = get_db_connection()
    if not conn: return

    try:
        cur = conn.cursor()
        # Updated SQL to match your exact column names:
        # event_type, actor, target_table, target_id, details, recorded_by, action_type
        cur.execute("""
            INSERT INTO audit_log (event_time, event_type, actor, target_table, target_id, details, recorded_by, action_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            ISO_NOW(), 
            event_type, # event_type
            actor,      # actor
            target_table, 
            target_id, 
            details, 
            actor,      # recorded_by (matching actor)
            event_type  # action_type (matching event_type for consistency)
        ))
        conn.commit()
    except Exception as e:
        logger.error(f"Audit log failure: {e}")
    finally:
        conn.close()



def find_students(search_term: str = "", include_inactive: bool = False, show_all: bool = False) -> List[Dict[str, Any]]:
    """
    Searches for students.
    - search_term: Name or ID to filter by.
    - include_inactive: If True, includes inactive students.
    - show_all: If True, returns ALL students (bypassing LIMIT 50).
    """
    conn = get_db_connection()
    if not conn:
        return []

    try:
        cur = conn.cursor()
        
        # Start building the query dynamically
        query = """
        SELECT 
            id, full_name, nickname, classroom, grade, total_points, phone, email, active
        FROM students
        WHERE 1=1
        """
        params = []

        # 1. Handle Search Term (Only apply if provided and NOT showing all)
        # If showing all, we ignore the search term to prevent conflicting logic
        if search_term and not show_all:
            safe_term = search_term.strip().lower().replace(' ', '%') 
            search_pattern = f"%{safe_term}%"
            query += " AND (full_name ILIKE %s OR CAST(id AS TEXT) ILIKE %s)"
            params.extend([search_pattern, search_pattern])

        # 2. Handle Inactive
        if not include_inactive:
            query += " AND active = TRUE"
            
        # 3. Order
        query += " ORDER BY full_name"

        # 4. Limit (Only apply if NOT showing all)
        if not show_all:
            query += " LIMIT 50"

        cur.execute(query, tuple(params))
        results = cur.fetchall()
        
        logger.info(f"Search (term='{search_term}', all={show_all}) returned {len(results)} students.")
        return results

    except Exception as e:
        logger.error(f"Database error during student search: {e}")
        return []
    finally:
        conn.close()


def get_student_by_id(student_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a single student by ID."""
    conn = get_db_connection()
    if not conn: return None

    try:
        cur = conn.cursor()
        # Note: Postgres boolean is TRUE/FALSE, not 1/0
        query = """
        SELECT * FROM students WHERE id = %s
        """
        cur.execute(query, (student_id,))
        row = cur.fetchone()
        return row
    except Exception as e:
        logger.error(f"Database error fetching student {student_id}:  {e}")
        return None
    finally:
        conn.close()

def update_student(db_path_ignored, student_id: int, update_fields: Dict[str, Any], modified_by: str) -> bool:
    """
    Updates fields in the students table.
    Note: db_path_ignored is kept for compatibility with old calls but not used.
    """
    conn = get_db_connection()
    if not conn: return False
    
    try:
        if not update_fields:
            return True

        cur = conn.cursor()
        
        # Add audit fields 
        # (Assuming your Supabase schema has these columns, if not, this part might need schema update)
        # For now, we update what we can.
        
        # Construct Dynamic SQL
        # Postgres uses %s
        set_clauses = [f"{k} = %s" for k in update_fields.keys()]
        
        sql = f"UPDATE students SET {', '.join(set_clauses)} WHERE id = %s"
        
        values = list(update_fields.values())
        values.append(student_id)

        cur.execute(sql, tuple(values))
        
        if cur.rowcount == 0:
            logger.warning(f"Update failed:  Student {student_id} not found.")
            return False

        conn.commit()
        
        write_audit(
            event_type="update_student_success", 
            actor=modified_by, 
            target_table="students", 
            target_id=student_id, 
            details=f"Updated fields: {list(update_fields.keys())}"
        )
        return True

    except Exception as e:
        logger.error(f"Error updating student {student_id}: {e}")
        write_audit(
            event_type="update_student_failed", 
            actor=modified_by, 
            target_table="students", 
            target_id=student_id, 
            details=str(e)
        )
        return False
    finally:
        conn.close()