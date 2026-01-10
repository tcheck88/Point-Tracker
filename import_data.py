import csv
import sys
import os
from datetime import datetime
from sqlalchemy import create_engine, MetaData, Table, select, insert

# ==========================================
# CONFIGURATION - PASTE YOUR CLOUD STRINGS HERE
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
    print(f"URL: {url}")
    confirm = input("Type 'YES' to confirm connection string is correct: ").strip()
    
    if confirm != 'YES':
        print("Aborted.")
        sys.exit(0)
        
    try:
        engine = create_engine(url, echo=False)
        connection = engine.connect()
        print("Connection Successful!")
        return engine, connection
    except Exception as e:
        print(f"\nConnection Failed: {e}")
        sys.exit(1)

def get_or_create_migration_activity(conn, activities_table):
    migration_name = "Migration / Initial Balance"
    sel = select(activities_table).where(activities_table.c.name == migration_name)
    result = conn.execute(sel).first()
    
    if result:
        return result.id
    
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
    """Returns a tuple: (user_id, username)"""
    # Try to find a user with role 'admin'
    sel = select(users_table).where(users_table.c.role == 'admin')
    result = conn.execute(sel).first()
    
    if result:
        # Assuming column 'username' exists
        return result.id, result.username
    
    # Fallback
    sel = select(users_table)
    result = conn.execute(sel).first()
    
    if result:
        return result.id, result.username
        
    print("Warning: No users found. Audits will be recorded as 'system'.")
    return None, "system"

def log_audit_event(conn, metadata, actor, target_table, target_id, details):
    """
    Inserts a row-level audit record matching the specific schema provided.
    """
    audit_table = metadata.tables.get('audit_log')
    if audit_table is None:
        return # Skip if table doesn't exist

    try:
        ins = insert(audit_table).values(
            event_time=datetime.utcnow(),
            event_type='IMPORT',      # Broad category
            action_type='CREATE',     # Specific action (like UI)
            actor=actor,              # The username
            target_table=target_table,
            target_id=target_id,
            details=details,
            recorded_by=actor         # Same as actor for imports
        )
        conn.execute(ins)
    except Exception as e:
        print(f"Audit Error: {e}")

def import_students(conn, metadata):
    filename = "students.csv"
    if not os.path.exists(filename):
        print(f"Error: {filename} not found.")
        return

    # Load Tables
    students = metadata.tables.get('student') or metadata.tables.get('students')
    transactions = metadata.tables.get('transaction') or metadata.tables.get('transactions')
    activities = metadata.tables.get('activity') or metadata.tables.get('activities')
    users = metadata.tables.get('user') or metadata.tables.get('users')

    if not students:
        print("Error: 'student' table not found.")
        return

    migration_activity_id = get_or_create_migration_activity(conn, activities)
    admin_id, admin_name = get_admin_user(conn, users)

    print(f"--- Importing Students from {filename} ---")
    
    count_new = 0
    with open(filename, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['Full Name'].strip()
            try:
                points = int(row['Initial Points']) if row['Initial Points'] else 0
            except ValueError:
                points = 0
            
            # Check exist
            sel = select(students).where(students.c.full_name == name)
            if conn.execute(sel).first():
                print(f"Skipping '{name}' (Already exists)")
                continue

            # 1. Insert Student
            ins = insert(students).values(
                full_name=name,
                balance=points, 
                active=True,
                classroom="",
                grade_level=""
            )
            result = conn.execute(ins)
            
            # Capture the new ID for the Audit Log
            new_student_id = result.inserted_primary_key[0]
            
            # 2. Insert Transaction (Financial History)
            if points > 0 and transactions is not None:
                ins_trans = insert(transactions).values(
                    student_id=new_student_id,
                    activity_id=migration_activity_id,
                    points=points,
                    description="Initial Balance Import",
                    user_id=admin_id,
                    timestamp=datetime.utcnow()
                )
                conn.execute(ins_trans)
            
            # 3. Log to Audit Trail (Row Level)
            log_audit_event(
                conn, metadata,
                actor=admin_name,
                target_table='student',
                target_id=new_student_id,
                details=f"Imported student: {name} (Initial Points: {points})"
            )
            
            print(f"Imported: {name}")
            count_new += 1
            
    conn.commit()
    print(f"Done. Imported {count_new} students.\n")

def import_prizes(conn, metadata):
    filename = "prizes.csv"
    if not os.path.exists(filename):
        print(f"Error: {filename} not found.")
        return

    # Look for 'prize_inventory'
    if 'prize_inventory' in metadata.tables:
        prizes = metadata.tables['prize_inventory']
        table_name_str = 'prize_inventory'
    elif 'prize' in metadata.tables:
        prizes = metadata.tables['prize']
        table_name_str = 'prize'
    else:
        print("Error: Could not find 'prize_inventory' table.")
        return

    users = metadata.tables.get('user') or metadata.tables.get('users')
    admin_id, admin_name = get_admin_user(conn, users)

    print(f"--- Importing Prizes from {filename} ---")

    count_new = 0
    with open(filename, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['Prize Name'].strip()
            try:
                cost = int(row['Cost']) if row['Cost'] else 0
                stock = int(row['Stock']) if row['Stock'] else 0
            except ValueError:
                cost, stock = 0, 0
            
            sel = select(prizes).where(prizes.c.name == name)
            if conn.execute(sel).first():
                print(f"Skipping '{name}' (Already exists)")
                continue

            # 1. Insert Prize
            ins = insert(prizes).values(
                name=name,
                point_cost=cost,  
                stock_count=stock, 
                active=True,
                last_modified_by='Import Utility'
            )
            result = conn.execute(ins)
            
            # Capture ID
            new_prize_id = result.inserted_primary_key[0]
            
            # 2. Log to Audit Trail (Row Level)
            log_audit_event(
                conn, metadata,
                actor=admin_name,
                target_table=table_name_str,
                target_id=new_prize_id,
                details=f"Imported prize: {name} (Cost: {cost}, Stock: {stock})"
            )

            print(f"Imported: {name}")
            count_new += 1

    conn.commit()
    print(f"Done. Imported {count_new} prizes.\n")

if __name__ == "__main__":
    # 1. Connect
    engine, conn = get_engine()
    
    # 2. Reflect Tables
    metadata = MetaData()
    metadata.reflect(bind=engine)
    
    # 3. Menu
    print("1. Import Students")
    print("2. Import Prizes")
    print("3. Exit")
    choice = input("Select: ")

    if choice == '1':
        import_students(conn, metadata)
    elif choice == '2':
        import_prizes(conn, metadata)
    
    conn.close()