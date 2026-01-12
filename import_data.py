import csv
import sys
import os
# NEW
from datetime import datetime, timezone
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

def get_or_create_migration_activity(conn, activities_table):
    """
    Ensures the 'Migration' activity exists so we can link it in the logs.
    """
    migration_name = "Migration / Initial Balance"
    # Check if exists
    sel = select(activities_table.c.id).where(activities_table.c.name == migration_name)
    result = conn.execute(sel).first()
    
    if result:
        return result[0] # Return the ID
    
    print(f"Creating system activity: '{migration_name}'...")
    ins = insert(activities_table).values(
        name=migration_name,
        description="System generated activity for initial data import.",
        default_points=0,
        active=True
    )
    result = conn.execute(ins)
    conn.commit()
    return result.inserted_primary_key[0]

def get_admin_user(conn, users_table):
    """
    Returns the username of an admin to record as the 'actor'.
    """
    if users_table is None:
        return "Import Utility"

    # Try to find a user with role 'admin' or 'sysadmin'
    try:
        sel = select(users_table.c.username).where(users_table.c.role.in_(['admin', 'sysadmin']))
        result = conn.execute(sel).first()
        if result:
            return result[0]
    except:
        pass
    
    return "Import Utility"


def log_audit_event(conn, metadata, actor, target_table, target_id, details, action_type="CREATE"):
    """
    Inserts into audit_log matching db_utils.py schema.
    Now accepts action_type (e.g., 'CREATE_STUDENT') to match app.py standards.
    """
    audit_table = metadata.tables.get('audit_log')
    if audit_table is None:
        return

    try:
        # FIX: Use timezone-aware timestamp
        now_utc = datetime.now(timezone.utc)
        
        ins = insert(audit_table).values(
            event_time=now_utc,
            event_type='IMPORT',
            action_type=action_type, # <--- UPDATED: Dynamic Action
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
    activities = metadata.tables.get('activities')
    users = metadata.tables.get('users')

    if students is None:
        print("Error: 'students' table not found in DB.")
        return

    # Setup helpers
    migration_act_id = None
    if activities is not None:
        migration_act_id = get_or_create_migration_activity(conn, activities)
    
    admin_name = get_admin_user(conn, users)

    print(f"--- Importing Students from {filename} ---")
    
    count_new = 0
    count_skipped = 0
    
    with open(filename, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        # Validation
        if 'Full Name' not in reader.fieldnames or 'Initial Points' not in reader.fieldnames:
            print(f"Error: CSV headers mismatch. Found: {reader.fieldnames}")
            return

        for row in reader:
            name = row['Full Name'].strip()
            try:
                p_str = row['Initial Points'].replace(',', '').strip()
                points = int(p_str) if p_str else 0
            except ValueError:
                points = 0
            
            # Check for existing
            sel = select(students.c.id).where(students.c.full_name == name)
            existing = conn.execute(sel).first()
            
            if existing:
                print(f"Skipping '{name}' (Already exists)")
                count_skipped += 1
                continue

            # 1. Insert Student
            ins = insert(students).values(
                full_name=name,
                total_points=points, 
                active=True,
                sms_consent=False,
                classroom="",
                grade="" 
            )
            result = conn.execute(ins)
            new_student_id = result.inserted_primary_key[0]
            
            # 2. Insert Transaction (into activity_log)
            if points > 0 and activity_log is not None:
                ins_log = insert(activity_log).values(
                    student_id=new_student_id,
                    activity_type="Migration / Initial Balance",
                    activity_id=migration_act_id,
                    points=points,
                    description="Imported from legacy data",
                    recorded_by=admin_name,
                    timestamp=datetime.now(timezone.utc)
                )
                conn.execute(ins_log)
            
            # 3. Log Audit (Action: CREATE_STUDENT)
            log_audit_event(
                conn, metadata,
                actor=admin_name,
                target_table='students',
                target_id=new_student_id,
                details=f"Imported student: {name} (Initial Points: {points})",
                action_type="CREATE_STUDENT"
            )
            
            print(f"Imported: {name}")
            count_new += 1
            
    conn.commit()
    print(f"\nSummary: Imported {count_new}, Skipped {count_skipped}.\n")

def import_prizes(conn, metadata):
    filename = "prizes.csv"
    if not os.path.exists(filename):
        # Fallback check for Capitalized filename
        if os.path.exists("Prizes.csv"):
            filename = "Prizes.csv"
        else:
            print(f"Error: {filename} not found.")
            return

    # Reflect Tables
    # Handle schema naming differences (prize vs prize_inventory)
    prizes = metadata.tables.get('prize_inventory')
    if not prizes:
        prizes = metadata.tables.get('prize')
    
    if prizes is None:
        print("Error: 'prize_inventory' table not found.")
        return

    users = metadata.tables.get('users')
    admin_name = get_admin_user(conn, users)

    print(f"--- Importing Prizes from {filename} ---")

    count_new = 0
    count_skipped = 0

    with open(filename, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Flexible Header Matching
            name = row.get('Prize Name') or row.get('Name')
            if not name: continue
            name = name.strip()

            try:
                c_str = (row.get('Cost') or row.get('Point Cost') or '0').replace(',', '')
                s_str = (row.get('Stock') or row.get('Stock Count') or '0').replace(',', '')
                cost = int(c_str)
                stock = int(s_str)
            except ValueError:
                cost, stock = 0, 0
            
            # Check Existing
            sel = select(prizes.c.id).where(prizes.c.name == name)
            if conn.execute(sel).first():
                print(f"Skipping '{name}' (Already exists)")
                count_skipped += 1
                continue

            # 1. Insert Prize
            # Note: 'last_modified_by' removed to match db_utils.py schema
            ins = insert(prizes).values(
                name=name,
                point_cost=cost,  
                stock_count=stock, 
                active=True,
                description=""
            )
            result = conn.execute(ins)
            new_prize_id = result.inserted_primary_key[0]
            
            # 2. Log Audit (Action: CREATE_PRIZE)
            log_audit_event(
                conn, metadata,
                actor=admin_name,
                target_table='prize_inventory',
                target_id=new_prize_id,
                details=f"Imported prize: {name} (Cost: {cost}, Stock: {stock})",
                action_type="CREATE_PRIZE" # <--- UPDATED
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
    
    while True:
        print("\n--- MENU ---")
        print("1. Import Students (Students.csv)")
        print("2. Import Prizes   (prizes.csv)")
        print("Q. Quit")
        choice = input("Choice: ").strip().lower()

        if choice == '1':
            import_students(conn, metadata)
        elif choice == '2':
            import_prizes(conn, metadata)
        elif choice == 'q':
            print("Goodbye.")
            break
        else:
            print("Invalid option.")
    
    conn.close()