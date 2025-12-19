import logging
import re
from db_utils import get_db_connection

logger = logging.getLogger(__name__)

# Validation Regex
PHONE_RE = re.compile(r'^(?:\+?52\s?)?(?:\(?\d{2,3}\)?[\s-]?){1}\d{7,8}$')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

def validate_inputs(data):
    """Returns (bool, list_of_errors)"""
    errors = []
    name = data.get('full_name', '').strip()
    
    if not name: errors.append("Full name is required.")
    elif len(name) < 2: errors.append("Name too short.")
    
    phone = data.get('phone', '')
    if phone and not PHONE_RE.match(phone.strip()):
        errors.append("Invalid Mexico phone format.")

    email = data.get('email', '')
    if email and not EMAIL_RE.match(email.strip()):
        errors.append("Invalid email format.")

    return len(errors) == 0, errors

def add_new_student(data):
    """
    Main entry point called by app.py.
    """
    # 1. Validate
    is_valid, errors = validate_inputs(data)
    if not is_valid:
        return False, "; ".join(errors)

    conn = get_db_connection()
    if not conn: return False, "DB Connection Failed"

    try:
        cur = conn.cursor()

        # 2. Check Duplicates (SQL way)
        # We look for matches on Email OR Phone OR Exact Name
        full_name = data['full_name'].strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()

        # Construct query dynamically to handle empty email/phone
        cur.execute("""
            SELECT id, full_name FROM students 
            WHERE (LOWER(full_name) = LOWER(%s))
            OR (LENGTH(%s) > 0 AND email = %s)
            OR (LENGTH(%s) > 0 AND phone = %s)
        """, (full_name, email, email, phone, phone))
        
        duplicates = cur.fetchall()
        if duplicates:
            logger.warning(f"Duplicate blocked: {duplicates}")
            return False, f"Potential duplicate found: {duplicates[0]['full_name']}"

        # 3. Insert
        cur.execute("""
            INSERT INTO students 
            (full_name, nickname, grade, classroom, parent_name, phone, email, sms_consent)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            full_name,
            data.get('nickname'),
            data.get('grade'),
            data.get('classroom'),
            data.get('parent_name'),
            phone,
            email,
            data.get('sms_consent', False)
        ))
        
        # We just need the ID to ensure it worked, though we don't return it currently
        new_id = cur.fetchone()['id']
        conn.commit()
        
        # Note: We do NOT log to audit_log here anymore. 
        # The main app.py handles logging to prevent schema mismatches.

        return True, "Student created successfully"

    except Exception as e:
        conn.rollback()
        logger.error(f"Error adding student: {e}")
        return False, str(e)
    finally:
        conn.close()