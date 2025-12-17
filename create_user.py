import sys
from werkzeug.security import generate_password_hash
from db_utils import get_db_connection

def create_user(username, password, role):
    # Validate role
    if role not in ['admin', 'staff']:
        print("Error: Role must be 'admin' or 'staff'")
        return

    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database.")
        return
    
    try:
        cur = conn.cursor()
        # Hash the password for security
        hashed_pw = generate_password_hash(password)
        
        cur.execute("""
            INSERT INTO users (username, password_hash, role)
            VALUES (%s, %s, %s)
        """, (username, hashed_pw, role))
        
        conn.commit()
        print(f"✅ Success! User '{username}' created with role '{role}'.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # Allow running from command line
    if len(sys.argv) == 4:
        create_user(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        print("\nInteractive Mode:")
        u = input("Enter Username: ")
        p = input("Enter Password: ")
        r = input("Enter Role (admin/staff): ")
        create_user(u, p, r)