import sys
from sqlalchemy import create_engine, text

# ==========================================
# CONFIGURATION
# ==========================================
DEV_DB_URL = "postgresql://postgres.ntpxnlcycykxfadzlgth:GTJ52AxK4Gc1ESHl@aws-1-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require" 
PROD_DB_URL = "postgresql://postgres.fecqimycokwmpfmfljbn:GTJ52AxK4Gc1ESHl@aws-1-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require" 

def get_engine():
    print("\n" + "="*50)
    print(" KUDOS IMPORT RESET UTILITY")
    print("="*50)
    print("This script removes students created by the Import Utility.")
    print("-" * 50)
    print("1. TEST DATABASE (Development)")
    print("2. PRODUCTION  (Use with caution!)")
    print("-" * 50)
    
    choice = input("Select Target Database (1 or 2): ").strip()
    
    if choice == '1':
        url = DEV_DB_URL
        env = "TEST/DEV"
    elif choice == '2':
        url = PROD_DB_URL
        env = "PRODUCTION"
    else:
        print("Invalid selection.")
        sys.exit(1)
        
    print(f"\nTARGET: [{env}]")
    confirm = input(f"Type 'DELETE' to confirm you want to remove imported students from {env}: ").strip()
    
    if confirm != 'DELETE':
        print("Aborted.")
        sys.exit(0)
        
    return create_engine(url)

def reset_imported_students():
    engine = get_engine()
    
    with engine.connect() as conn:
        print("\nScanning for imported students...")
        
        # 1. Identify Students to Delete
        # We find students who have a 'Migration / Initial Balance' transaction
        # This prevents accidental deletion of manually added students.
        find_sql = text("""
            SELECT DISTINCT s.id, s.full_name 
            FROM students s
            JOIN activity_log al ON s.id = al.student_id
            WHERE al.activity_type = 'Migration / Initial Balance'
        """)
        
        students_to_delete = conn.execute(find_sql).fetchall()
        
        if not students_to_delete:
            print("No imported students found (checked for 'Migration / Initial Balance' activity).")
            return

        print(f"Found {len(students_to_delete)} students to remove:")
        ids = [row[0] for row in students_to_delete]
        for row in students_to_delete:
            print(f" - {row[1]} (ID: {row[0]})")
            
        final_confirm = input(f"\nProceed with deletion of {len(ids)} students? (y/n): ").lower()
        if final_confirm != 'y':
            print("Cancelled.")
            return

        # Format IDs for SQL IN clause
        id_tuple = tuple(ids)
        # Handle single item tuple syntax (1,)
        if len(ids) == 1:
            id_tuple = f"({ids[0]})"
        
        try:
            # 2. Delete Audit Logs (Cleanup the evidence of the import)
            # A. Delete audits for the specific students
            print("Cleaning Audit Log (Student Creation)...")
            conn.execute(text(f"""
                DELETE FROM audit_log 
                WHERE target_table = 'students' AND target_id IN {id_tuple}
            """))

            # B. Delete audits for the specific transactions (Point Awards)
            print("Cleaning Audit Log (Migration Points)...")
            conn.execute(text(f"""
                DELETE FROM audit_log 
                WHERE target_table = 'activity_log' 
                AND target_id IN (
                    SELECT id FROM activity_log WHERE student_id IN {id_tuple}
                )
            """))

            # 3. Delete Activity History (Foreign Key Requirement)
            print("Removing Student History...")
            conn.execute(text(f"DELETE FROM activity_log WHERE student_id IN {id_tuple}"))

            # 4. Delete Students
            print("Removing Students...")
            conn.execute(text(f"DELETE FROM students WHERE id IN {id_tuple}"))
            
            conn.commit()
            print("\nSuccess! Import rolled back.")
            
        except Exception as e:
            print(f"Error during deletion: {e}")
            conn.rollback()

if __name__ == "__main__":
    reset_imported_students()