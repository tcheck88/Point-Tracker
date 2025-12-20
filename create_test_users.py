from werkzeug.security import generate_password_hash
from db_utils import get_db_connection

def create_user(username, password, role):
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to DB.")
        return

    try:
        cur = conn.cursor()
        pw_hash = generate_password_hash(password)
        
        # Check if user exists
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        exists = cur.fetchone()
        
        if exists:
            print(f"Updating existing user: {username}")
            cur.execute("""
                UPDATE users SET password_hash = %s, role = %s WHERE username = %s
            """, (pw_hash, role, username))
        else:
            print(f"Creating new user: {username}")
            cur.execute("""
                INSERT INTO users (username, password_hash, role)
                VALUES (%s, %s, %s)
            """, (username, pw_hash, role))
            
        conn.commit()
        print(f"Success: {username} ({role}) is ready.")
        
    except Exception as e:
        print(f"Error creating {username}: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # 1. Create Test Admin
    create_user("Test_Admin", "Admin123!", "sysadmin") 
    
    # 2. Create Test Staff
    create_user("Test_Staff", "Staff123!", "staff")
    
    print("\nDone! You can now log in with these credentials.")