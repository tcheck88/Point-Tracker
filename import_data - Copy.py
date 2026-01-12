import csv
import sys
import os
from datetime import datetime
from sqlalchemy import create_engine, MetaData, Table, select, insert

# ==========================================
# CONFIGURATION
# ==========================================

# 1. DEVELOPMENT (Cloud)
DEV_DB_URL = "postgresql://postgres.ntpxnlcycykxfadzlgth:GTJ52AxK4Gc1ESHl@aws-1-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require" 

# 2. PRODUCTION (Cloud)
PROD_DB_URL = "postgresql://postgres.fecqimycokwmpfmfljbn:GTJ52AxK4Gc1ESHl@aws-1-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require" 

# ==========================================

def get_engine():
    print("\n" + "="*50)
    print(" KUDOS STANDALONE IMPORT UTILITY")
    print("="*50)
    print("1. DEVELOPMENT (Cloud)")
    print("2. PRODUCTION  (Cloud)")
    print("-" * 50)
    
    choice = input("Select Target Database (1 or 2): ").strip()
    
    if choice == '1':
        url = DEV_DB_URL
        env = "DEVELOPMENT"
    elif choice == '2':
        url = PROD_DB_URL
        env = "PRODUCTION"
    else:
        print("Invalid selection.")
        sys.exit(1)
        
    print(f"\nWARNING: You are about to write to: [{env}]")
    confirm = input("Type 'YES' to confirm: ").strip()
    
    if confirm != 'YES':
        print("Aborted.")
        sys.exit(0)
        
    try:
        engine = create_engine(url)
        connection = engine.connect()
        print("Connection Successful!")
        return engine, connection
    except Exception as e:
        print(f"\nConnection Failed: {e}")
        sys.exit(1)

def log_audit_event(conn, metadata, actor, target_table, target_id, details):
    """
    Inserts into audit_log matching db_utils.py schema
    """
    audit_table = metadata.tables.get('audit_log')
    if audit_table is None:
        print("Warning: audit_log table not found")
        return

    try:
        ins = insert(audit_table).values(
            event_time=datetime.utcnow(),
            event_type='IMPORT',
            action_type='CREATE',
            actor=actor,
            recorded_by=actor,
            target_table=target_table,
            target_id=target_id,
            details=details
        )
        conn.execute(ins)
    except Exception as e:
        print(f"Audit Error: {e}")

def import_students(conn, metadata):
    # CORRECTION: Matches uploaded filename case
    filename = "Students.csv"
    if not os.path.exists(filename):
        # Fallback for lowercase
        if os.path.exists("students.csv"):
            filename = "students.csv"
        else:
            print(f"Error: {filename} not found.")
            return

    # Reflect Tables
    students = metadata.tables.get('students')
    activity_log = metadata.tables.get('activity_log')

    if students is None:
        print("Error: 'students' table not found in DB.")
        return

    print(f"--- Importing Students from {filename} ---")
    
    count_new = 0
    count_skipped = 0
    
    # Use encoding utf-8-sig to handle BOM if present
    with open(filename, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        # Verify Headers
        if 'Full Name' not in reader.fieldnames or 'Initial Points' not in reader.fieldnames:
            print(f"Error: CSV headers mismatch. Found: {reader.fieldnames}")
            return

        for row in reader:
            name = row['Full Name'].strip()
            try:
                # Handle commas in numbers (e.g., "1,000")
                p_str = row['Initial Points'].replace(',', '').strip()
                points = int(p_str) if p_str else 0
            except ValueError:
                points = 0
            
            # Check for existing student
            sel = select(students.c.id).where(students.c.full_name == name)
            existing = conn.execute(sel).first()
            
            if existing:
                print(f"Skipping '{name}' (Already exists)")
                count_skipped += 1
                continue

            # 1. Insert Student
            # CORRECTION: Uses 'total_points' instead of 'balance'
            ins = insert(students).values(
                full_name=name,
                total_points=points, 
                active=True,
                sms_consent=False
            )
            result = conn.execute(ins)
            
            # Capture the new ID
            new_student_id = result.inserted_primary_key[0]
            
            # 2. Insert Initial Balance History
            # CORRECTION: Writes to activity_log with correct columns
            if points > 0 and activity_log is not None:
                ins_log = insert(activity_log).values(
                    student_id=new_student_id,
                    activity_type="Migration / Initial Balance", # Text based type
                    points=points,
                    description="Imported from legacy data",
                    recorded_by="Import Utility",
                    timestamp=datetime.utcnow()
                )
                conn.execute(ins_log)
            
            # 3. Log to Audit Trail
            log_audit_event(
                conn, metadata,
                actor="Import Utility",
                target_table='students',
                target_id=new_student_id,
                details=f"Imported student: {name} (Initial Points: {points})"
            )
            
            print(f"Imported: {name}")
            count_new += 1
            
    conn.commit()
    print(f"\nSummary: Imported {count_new}, Skipped {count_skipped}.\n")

if __name__ == "__main__":
    # 1. Connect
    engine, conn = get_engine()
    
    # 2. Reflect Tables
    metadata = MetaData()
    metadata.reflect(bind=engine)
    
    # 3. Menu
    print("1. Import Students (Students.csv)")
    print("2. Exit")
    choice = input("Select: ").strip()

    if choice == '1':
        import_students(conn, metadata)
    else:
        print("Exiting.")
    
    conn.close()