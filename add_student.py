"""
add_student.py

Updated module: Mexico phone validation, email validation, parent_name, sms_consent fields,
duplicate detection includes email boosting, audit logging.
"""

import sqlite3
import re
import datetime
import difflib
from typing import Optional, Dict, Any, List, Tuple

ISO_NOW = lambda: datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

# -----------------------
# DB init
# -----------------------
def init_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS Students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        nickname TEXT,
        phone TEXT,
        email TEXT,
        parent_name TEXT,
        sms_consent INTEGER NOT NULL DEFAULT 0,
        classroom TEXT,
        grade TEXT,
        language_preference TEXT,
        total_points INTEGER NOT NULL DEFAULT 0,
        referral_code TEXT,
        created_by TEXT,
        created_at TEXT,
        modified_by TEXT,
        modified_at TEXT,
        merge_into INTEGER,
        merge_justification TEXT,
        active INTEGER NOT NULL DEFAULT 1
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS Audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_time TEXT NOT NULL,
        event_type TEXT NOT NULL,
        actor TEXT,
        target_table TEXT,
        target_id INTEGER,
        details TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS Duplicate_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_time TEXT NOT NULL,
        checked_name TEXT,
        checked_phone TEXT,
        checked_email TEXT,
        matches TEXT,
        actor TEXT,
        action_taken TEXT,
        justification TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS Transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        date TEXT,
        activity TEXT,
        points INTEGER,
        performed_by TEXT
    )
    """)
    conn.commit()
    conn.close()


# -----------------------
# Validation rules
# -----------------------
# Mexico phone regex: optional +52, then 10 national digits (allowing common separators)
PHONE_RE = re.compile(r'^(?:\+?52\s?)?(?:\(?\d{2,3}\)?[\s-]?){1}\d{7,8}$')

# Email regex (reasonable practical validation)
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

def validate_inputs(full_name: str,
                    nickname: Optional[str],
                    phone: Optional[str],
                    email: Optional[str],
                    parent_name: Optional[str],
                    sms_consent: Optional[bool],
                    classroom: Optional[str],
                    grade: Optional[str]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    name = (full_name or "").strip()
    if not name:
        errors.append("Full name is required.")
    else:
        if len(name) < 2 or len(name) > 200:
            errors.append("Full name must be between 2 and 200 characters.")
        if name.isnumeric():
            errors.append("Full name must include letters, not only numbers.")

    if nickname:
        if len(nickname.strip()) > 100:
            errors.append("Nickname must be 100 characters or fewer.")

    if phone:
        if not PHONE_RE.match(phone.strip()):
            errors.append("Phone number format looks invalid for Mexico. Expected 10-digit national number with optional +52.")

    if email:
        if len(email.strip()) > 254 or not EMAIL_RE.match(email.strip()):
            errors.append("Email format looks invalid.")

    if parent_name:
        if len(parent_name.strip()) > 200:
            errors.append("Parent name must be 200 characters or fewer.")

    if sms_consent is not None and not isinstance(sms_consent, bool):
        errors.append("SMS consent must be a boolean value.")

    if classroom:
        if len(classroom.strip()) > 100:
            errors.append("Classroom value must be 100 characters or fewer.")

    if grade:
        if len(grade.strip()) > 50:
            errors.append("Grade value must be 50 characters or fewer.")

    return (len(errors) == 0, errors)


# -----------------------
# Duplicate detection
# -----------------------
def find_possible_duplicates(db_path: str, name: Optional[str], phone: Optional[str], email: Optional[str], max_results: int = 5) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, name, phone, email, classroom FROM Students WHERE active=1")
    rows = c.fetchall()
    conn.close()

    candidates: List[Dict[str, Any]] = []
    name_norm = (name or "").strip().lower()
    phone_norm = (phone or "").strip()
    email_norm = (email or "").strip().lower()

    for r in rows:
        candidate_name = (r["name"] or "").strip().lower()
        score = 0.0
        if name_norm and candidate_name:
            score = difflib.SequenceMatcher(a=name_norm, b=candidate_name).ratio()
        candidate_phone = (r["phone"] or "").strip()
        candidate_email = (r["email"] or "").strip().lower()
        # boost score on exact phone or email match
        if phone_norm and candidate_phone and phone_norm == candidate_phone:
            score = max(score, 0.97)
        if email_norm and candidate_email and email_norm == candidate_email:
            score = max(score, 0.99)

        if score > 0.45:
            candidates.append({
                "id": r["id"],
                "name": r["name"],
                "phone": r["phone"],
                "email": r["email"],
                "classroom": r["classroom"],
                "confidence": int(round(score * 100))
            })

    candidates.sort(key=lambda x: x["confidence"], reverse=True)
    return candidates[:max_results]


# -----------------------
# Audit logging helper
# -----------------------
def write_audit(db_path: str,
                event_type: str,
                actor: Optional[str],
                target_table: Optional[str],
                target_id: Optional[int],
                details: Optional[str]) -> None:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
    INSERT INTO Audit_log (event_time, event_type, actor, target_table, target_id, details)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (ISO_NOW(), event_type, actor, target_table, target_id, details))
    conn.commit()
    conn.close()


# -----------------------
# Core: add_student
# -----------------------
def add_student(db_path: str,
                full_name: str,
                nickname: Optional[str] = None,
                phone: Optional[str] = None,
                email: Optional[str] = None,
                parent_name: Optional[str] = None,
                sms_consent: Optional[bool] = False,
                classroom: Optional[str] = None,
                grade: Optional[str] = None,
                created_by: Optional[str] = None,
                allow_create_on_duplicate: bool = False,
                duplicate_justification: Optional[str] = None
                ) -> Dict[str, Any]:
    write_audit(db_path, event_type="validation_start", actor=created_by, target_table="Students", target_id=None,
                details=f"Starting validation for name={full_name!r}, phone={phone!r}, email={email!r}")

    is_valid, errors = validate_inputs(full_name, nickname, phone, email, parent_name, sms_consent, classroom, grade)
    if not is_valid:
        write_audit(db_path, event_type="validation_failed", actor=created_by, target_table="Students", target_id=None,
                    details=f"Validation failed: {errors}")
        return {"success": False, "message": "Validation failed", "errors": errors}

    write_audit(db_path, event_type="validation_success", actor=created_by, target_table="Students", target_id=None,
                details="Validation passed")

    # Duplicate check
    write_audit(db_path, event_type="duplicate_check_start", actor=created_by, target_table="Students", target_id=None,
                details=f"Checking duplicates for name={full_name!r}, phone={phone!r}, email={email!r}")
    duplicates = find_possible_duplicates(db_path, full_name, phone, email)
    write_audit(db_path, event_type="duplicate_check_result", actor=created_by, target_table="Students", target_id=None,
                details=f"Found {len(duplicates)} potential matches")

    if duplicates:
        import json
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""
        INSERT INTO Duplicate_log (event_time, checked_name, checked_phone, checked_email, matches, actor, action_taken, justification)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ISO_NOW(), full_name, phone, email, json.dumps(duplicates), created_by, "checked", None))
        conn.commit()
        conn.close()

        if not allow_create_on_duplicate:
            write_audit(db_path, event_type="create_blocked_duplicate", actor=created_by, target_table="Students",
                        target_id=None, details="Creation blocked due to potential duplicates; user must confirm override")
            return {
                "success": False,
                "message": "Potential duplicates found",
                "duplicates": duplicates,
                "errors": None
            }
        else:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("""
            UPDATE Duplicate_log SET action_taken = ?, justification = ?, actor = ? WHERE id = (
              SELECT id FROM Duplicate_log ORDER BY id DESC LIMIT 1
            )
            """, ("override_create", duplicate_justification or "", created_by))
            conn.commit()
            conn.close()
            write_audit(db_path, event_type="create_override_recorded", actor=created_by, target_table="Students",
                        target_id=None, details=f"Override justification recorded: {duplicate_justification}")

   
    # Insert the student record
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        write_audit(db_path, event_type="create_student_start", actor=created_by, target_table="Students", target_id=None,
                    details=f"Inserting student record for {full_name!r}")
        now = ISO_NOW()
        c.execute("""
        INSERT INTO Students
        (name, nickname, phone, email, parent_name, sms_consent, classroom, grade, total_points, referral_code, created_by, created_at, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?, 1)
        """, (
            full_name.strip(),
            (nickname or None),
            (phone or None),
            (email or None),
            (parent_name or None),
            (1 if sms_consent else 0),
            (classroom or None),
            (grade or None),
            (created_by or None),
            now
        ))
        student_id = c.lastrowid
        conn.commit()
        conn.close()

        write_audit(db_path, event_type="create_student_success", actor=created_by, target_table="Students", target_id=student_id,
                    details=f"Student created with id={student_id}")

        return {
            "success": True,
            "message": "Student created",
            "student_id": student_id, 
            "duplicates": duplicates if duplicates else []
        }

    except Exception as ex:
        log_id = locals().get('student_id', 'Unknown')
        write_audit(db_path, event_type="create_student_failed", actor=created_by, target_table="Students", target_id=None,
                    details=f"Error inserting student (ID: {log_id}): {str(ex)}")
        return {"success": False, "message": "Database error during creation", "errors": [str(ex)]}