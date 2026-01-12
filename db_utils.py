# db_utils.py

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def get_db_connection():
    # ... (Keep your existing connection logic here) ...
    # ... (Copy the connection code from your current file) ...
    # Placeholder for brevity:
    prod_url = "postgresql://postgres.ntpxnlcycykxfadzlgth:GTJ52AxK4Gc1ESHl@aws-1-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require"
    db_url = os.getenv("DATABASE_URL", prod_url)
    try:
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=10)
        return conn
    except Exception as e:
        logger.error(f"DB Connection failed: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if not conn:
        logger.critical("Cannot initialize DB: No connection.")
        return

    try:
        cur = conn.cursor()
        
        # 1. Students
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
                total_points INTEGER DEFAULT 0,
                active BOOLEAN DEFAULT TRUE
            );
        """)

        # 2. Activities Catalog
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                default_points INTEGER DEFAULT 0,
                active BOOLEAN DEFAULT TRUE
            );
        """)

        # 3. Prize Inventory
        cur.execute("""
            CREATE TABLE IF NOT EXISTS prize_inventory (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                point_cost INTEGER DEFAULT 0,
                stock_count INTEGER DEFAULT 0,
                active BOOLEAN DEFAULT TRUE
            );
        """)

        # 4. Activity Log (Now with FKs)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES students(id),
                activity_type TEXT NOT NULL,
                points INTEGER NOT NULL,
                description TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                recorded_by TEXT,
                activity_id INTEGER REFERENCES activities(id) ON DELETE SET NULL,
                prize_id INTEGER REFERENCES prize_inventory(id) ON DELETE SET NULL
            );
        """)

        # --- MIGRATION: Auto-add columns if they don't exist (Safely) ---
        cur.execute("""
            ALTER TABLE activity_log ADD COLUMN IF NOT EXISTS activity_id INTEGER REFERENCES activities(id) ON DELETE SET NULL;
            ALTER TABLE activity_log ADD COLUMN IF NOT EXISTS prize_id INTEGER REFERENCES prize_inventory(id) ON DELETE SET NULL;
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
        
        # 6. System Settings
        cur.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT,
                description TEXT
            );
        """)
        cur.execute("INSERT INTO system_settings (setting_key, setting_value) VALUES ('POINT_ALERT_THRESHOLD', '500') ON CONFLICT DO NOTHING;")

        conn.commit()
        logger.info("Database initialized/migrated successfully.")
    except Exception as e:
        conn.rollback()
        logger.critical(f"DB Init Failed: {e}")
    finally:
        conn.close()