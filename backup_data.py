import os
import subprocess
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from local .env file
load_dotenv()

def get_target_db():
    """
    Asks the user to select which environment to backup.
    Returns the corresponding connection string.
    """
    prod_url = os.getenv("PROD_DATABASE_URL")
    dev_url = os.getenv("DEV_DATABASE_URL")
    # Fallback for legacy .env setup
    generic_url = os.getenv("DATABASE_URL")

    print("\n--- Select Database to Backup ---")
    options = {}
    
    if prod_url:
        print("1. [PRODUCTION] (PROD_DATABASE_URL)")
        options['1'] = ("Production", prod_url)
    if dev_url:
        print("2. [DEVELOPMENT] (DEV_DATABASE_URL)")
        options['2'] = ("Development", dev_url)
    if generic_url and not prod_url:
        # Only show generic if PROD isn't defined to avoid confusion
        print("3. [GENERIC] (DATABASE_URL from .env)")
        options['3'] = ("Generic", generic_url)

    if not options:
        print("❌ Error: No database URLs found in .env file.")
        print("   Action: Add PROD_DATABASE_URL or DEV_DATABASE_URL to your local .env file.")
        return None, None

    choice = input("\nEnter choice (1/2/3): ").strip()
    
    if choice in options:
        return options[choice]
    else:
        print("❌ Invalid choice.")
        return None, None

def backup_database():
    """
    Orchestrates the backup process using pg_dump.
    """
    # 1. Select Environment
    env_name, db_url = get_target_db()
    if not db_url:
        return

    # 2. Create Timestamped Filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = "backups"
    
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # Filename includes environment name (e.g., backup_Production_2025-01-07...)
    filename = os.path.join(backup_dir, f"backup_{env_name}_{timestamp}.sql")

    # 3. Run pg_dump
    print(f"\n⏳ Connecting to {env_name}...")
    print(f"⏳ Downloading data to: {filename}...")
    
    # Copy local environment for subprocess
    env = os.environ.copy()
    
    try:
        # pg_dump arguments:
        # --clean: Include commands to DROP databases/tables before creating them (good for restores)
        # --if-exists: Prevents errors if the dropped objects don't exist
        # --no-owner / --no-acl: Skips ownership/privilege commands (avoids permission errors on restore)
        subprocess.run(
            ["pg_dump", db_url, "--clean", "--if-exists", "--no-owner", "--no-acl", "-f", filename],
            check=True,
            env=env
        )
        print(f"✅ SUCCESS! Backup saved.")
        print(f"   File: {os.path.abspath(filename)}")
        print("   Recommendation: Upload this file to secure cloud storage immediately.")

    except subprocess.CalledProcessError as e:
        print(f"\n❌ BACKUP FAILED.")
        print(f"   Error code: {e}")
        print("   Troubleshooting:")
        print("   1. Is the password in your .env file correct?")
        print("   2. Is your IP address allowed in Supabase? (Check 'Network Restrictions' in Supabase Dashboard)")
    except FileNotFoundError:
        print("\n❌ Error: 'pg_dump' command not found.")
        print("   Action: Ensure you added the PostgreSQL 'bin' folder to your System PATH.")

if __name__ == "__main__":
    try:
        backup_database()
        # Keep window open if running via double-click
        print("\n(Press Enter to exit)")
        input()
    except KeyboardInterrupt:
        print("\nOperation cancelled.")