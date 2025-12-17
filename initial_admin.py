# create_admin.py
from werkzeug.security import generate_password_hash
from db_utils import get_db_connection

def create_admin(username, password):
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to the database.")
        return
    cur = conn.cursor()
    pw_hash = generate_password_hash(password)
    
    try:
        cur.execute("""
            INSERT INTO users (username, password_hash, role)
            VALUES (%s, %s, 'admin')
            ON CONFLICT (username) DO NOTHING
        """, (username, pw_hash))
        conn.commit()
        print(f"Admin user '{username}' created successfully.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # Update these credentials for your first login
    create_admin("admin", "Leermexico2025!")