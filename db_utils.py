import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def get_db_connection():
    """Establishes connection to Supabase (PostgreSQL) with a safety timeout."""
    
    # 1. Production Database URL (Fallback)
    # REPLACE THIS with your actual Production connection string
    # We added '?sslmode=require' to the end to ensure security
    prod_url = "postgresql://postgres.YOUR_USER:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
    
    # 2. Get URL: Try .env first (Dev), otherwise use Prod Fallback
    db_url = os.getenv("DATABASE_URL", prod_url)

    if not db_url:
        logger.error("DATABASE_URL is missing.")
        return None

    try:
        # Mask password for logging
        safe_url = db_url.split('@')[1] if '@' in db_url else 'UNKNOWN'
        print(f"DEBUG: Attempting connection to {safe_url}")
        
        conn = psycopg2.connect(
            db_url, 
            cursor_factory=RealDictCursor, 
            connect_timeout=5
        )
        print("DEBUG: Connection Successful")
        return conn
    except Exception as e:
        logger.error(f"DATABASE CONNECTION FAILURE: {e}")
        return None

def init_db():
    """Creates all necessary tables in Supabase."""
    conn = get_db_connection()
    if not conn: return

    try:
        cur = conn.cursor()
        
        # 1. Users (Admins)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'staff',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Students
        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY,
                full_name TEXT NOT NULL,
                nickname TEXT,
                grade TEXT,
                classroom TEXT,
                parent_name TEXT,
                phone TEXT,
                email TEXT,
                sms_consent BOOLEAN DEFAULT FALSE,
                active BOOLEAN DEFAULT TRUE,
                total_points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. Activity Log (Points)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES students(id),
                activity_type TEXT NOT NULL,
                points INTEGER NOT NULL,
                description TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Activities (Catalog)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                default_points INTEGER DEFAULT 0,
                active BOOLEAN DEFAULT TRUE
            );
        """)

        # 5. Audit Log
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT,
                action_type TEXT,
                actor TEXT,
                recorded_by TEXT,
                target_table TEXT,
                target_id INTEGER,
                details TEXT
            );
        """)

        conn.commit()
        logger.info("Database tables checked/initialized successfully.")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        conn.rollback()
    finally:
        conn.close()