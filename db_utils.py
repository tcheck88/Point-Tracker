# db_utils.py
import sqlite3
from typing import Optional

def enable_wal_and_timeout(db_path: str, busy_timeout_ms: int = 5000) -> None:
    """
    Enable WAL journal_mode and set busy_timeout for the given SQLite DB file.
    Safe to run repeatedly.
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        cur = conn.cursor()
        # Enable WAL - returns 'wal' or current mode
        cur.execute("PRAGMA journal_mode=WAL;")
        # Set busy timeout (milliseconds)
        cur.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)};")
        conn.commit()
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import os
    DB = os.path.join(os.path.dirname(__file__), "leer_mexico.db")
    enable_wal_and_timeout(DB)
    print("WAL enabled and busy_timeout set.")