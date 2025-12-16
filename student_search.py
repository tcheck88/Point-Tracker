import sqlite3
import datetime
import logging
from typing import List, Dict, Any, Optional

# CHANGED: Initialize logger for this module
logger = logging.getLogger(__name__)

ISO_NOW = lambda: datetime.datetime.utcnow().isoformat() + 'Z'

# Utility to log changes, based on schema in other files
def write_audit(db_path: str, event_type: str, actor: str, target_table: str, target_id: Optional[int], details: str) -> None:
    """
    Helper function to write an entry to the Audit_log table.
    This function has its own robust error handling.
    """
    try:
        conn = sqlite3.connect(db_path)
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
        conn.commit()
        conn.close()
    except Exception as e:
        # CHANGED: Replaced print() with logger.error() to prevent stdout corruption
        logger.error(f"ERROR: Failed to write audit log: {e}")

# Corrected search_students function
def search_students(db_path: str, search_term: str) -> List[Dict[str, Any]]:
    """Searches the Students table for students matching the search term."""
    
    # FIX 1: Ensure case-insensitivity by converting the search term to lowercase.
    # We replace spaces with '%' to allow multi-word searches like "test stu" to find "Test Student".
    safe_term = search_term.strip().lower().replace(' ', '%') 
    search_pattern = f"%{safe_term}%" 

    conn = None
    results = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        query = """
        SELECT 
            id, name, nickname, phone, email, 
            total_points, classroom, grade, active
        FROM Students
        WHERE 
            -- FIX 2: Use LOWER(name) with the lowercased search pattern for case-insensitive matching
            (LOWER(name) LIKE ? OR CAST(id AS TEXT) LIKE ?)
            AND active = 1
        ORDER BY name
        LIMIT 50
        """
        # Pass the lowercased search pattern for both name and ID
        c.execute(query, (search_pattern, search_pattern,))
        
        # CHANGED: Full result processing for better data structure
        results = [dict(row) for row in c.fetchall()]
        
        logger.info(f"Search for '{search_term}' returned {len(results)} students.")
        
        return results

    except Exception as e:
        # CHANGED: Replaced print() with logger.error()
        logger.error(f"Database error during student search for term '{search_term}': {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_student_by_id(db_path: str, student_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a single student from the Students table by their ID."""
    conn = None
    result = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        query = """
        SELECT 
            id, name, nickname, phone, email, parent_name, sms_consent,
            total_points, classroom, grade, active, created_at, created_by,
            modified_at, modified_by
        FROM Students -- Table name is consistent with the standard
        WHERE 
            id = ?
        """
        c.execute(query, (student_id,))
        
        row = c.fetchone()
        if row:
            result = dict(row)

    except Exception as e:
        logger.error(f"Database error during student fetch by ID {student_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()
            
    return result

def update_student(db_path: str, student_id: int, update_fields: Dict[str, Any], modified_by: str) -> bool:
    """
    Updates fields in the Students table for a given student ID.
    update_fields should be a dict of {column_name: new_value}.
    """
    conn = None
    try:
        if not update_fields:
            logger.warning(f"Attempted to update student ID {student_id} with no fields.")
            return True # Nothing to do

        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Add audit fields automatically
        update_fields['modified_at'] = ISO_NOW()
        update_fields['modified_by'] = modified_by

        set_clauses = [f"{k} = ?" for k in update_fields.keys()]
        # CRITICAL FIX 3: Changed table name from 'Users' to 'Students'
        sql = f"UPDATE Students SET {', '.join(set_clauses)} WHERE id = ?"
        
        values = list(update_fields.values())
        values.append(student_id)

        c.execute(sql, tuple(values))
        
        if c.rowcount == 0:
            # CRITICAL FIX 4: Changed table name from 'user ID' to 'student ID' and 'User not found'
            logger.warning(f"Update failed for student ID {student_id}: Student not found.")
            return False

        conn.commit()
        
        # CRITICAL FIX 5: Changed target_table from 'Users' to 'Students' in audit log
        write_audit(
            db_path, 
            event_type="update_student_success", 
            actor=modified_by, 
            target_table="Students", 
            target_id=student_id, 
            details=f"Student profile updated. Fields: {list(update_fields.keys())}"
        )

        return True

    except Exception as e:
        # CHANGED: Replaced print() with logger.error()
        logger.error(f"Database error during student update for ID {student_id}: {e}")
        # CRITICAL FIX 6: Changed target_table from 'Users' to 'Students' in audit log
        write_audit(
            db_path, 
            event_type="update_student_failed", 
            actor=modified_by, 
            target_table="Students", 
            target_id=student_id, 
            details=f"Update failed due to error: {e}"
        )
        return False
    finally:
        if conn:
            conn.close()