import datetime
import logging
from typing import List, Dict, Any, Optional
from db_utils import get_db_connection

logger = logging.getLogger(__name__)

ISO_NOW = lambda: datetime.datetime.utcnow().isoformat() + 'Z'

def write_audit(event_type: str, actor: str, target_table: str, target_id: Optional[int], details: str) -> None:
    """
    Writes an entry to the audit_log table in Supabase.
    """
    conn = get_db_connection()
    if not conn:
        logger.error("Failed to connect to DB for audit log.")
        return

    try:
        cur = conn.cursor()
        # Ensure audit table exists (simple check to prevent crash if migration missed)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                event_time TIMESTAMP,
                event_type TEXT,
                actor TEXT,
                target_table TEXT,
                target_id INTEGER,
                details TEXT
            )
        """)
        
        cur.execute("""
            INSERT INTO audit_log (event_time, event_type, actor, target_table, target_id, details)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            ISO_NOW(),
            event_type,
            actor,
            target_table,
            target_id,
            details
        ))
        conn.commit()
    except Exception as e:
        logger.error(f"ERROR: Failed to write audit log: {e}")
    finally:
        conn.close()

def find_students(search_term: str) -> List[Dict[str, Any]]:
    """
    Searches for students matching the search term (Name or ID).
    Compatible with Supabase/PostgreSQL.
    """
    # PRESERVED LOGIC: Multi-word search handling
    safe_term = search_term.strip().lower().replace(' ', '%') 
    search_pattern = f"%{safe_term}%" 

    conn = get_db_connection()
    if not conn:
        return []

    try:
        cur = conn.cursor()
        
        # PRESERVED LOGIC: Case-insensitive search on Name AND ID
        # PostgreSQL uses %s for placeholders
        query = """
        SELECT 
            id, full_name, nickname, phone, email, 
            classroom, grade, active
        FROM students
        WHERE 
            (LOWER(full_name) LIKE %s OR CAST(id AS TEXT) LIKE %s)
            AND active = TRUE
        ORDER BY full_name
        LIMIT 50
        """
        cur.execute(query, (search_pattern, search_pattern))
        
        # RealDictCursor returns dictionary-like objects automatically
        results = cur.fetchall()
        
        logger.info(f"Search for '{search_term}' returned {len(results)} students.")
        return results

    except Exception as e:
        logger.error(f"Database error during student search for term '{search_term}': {e}")
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
        logger.error(f"Database error fetching student {student_id}: {e}")
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
            logger.warning(f"Update failed: Student {student_id} not found.")
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