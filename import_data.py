import csv
import sys
import os
from datetime import datetime

# Setup Flask Context
from app import app
from db_session import db
from models import Student, Activity, Transaction, User, Prize

def get_or_create_migration_activity():
    """Ensures the specific activity for initial balances exists."""
    migration_name = "Migration / Initial Balance"
    
    activity = Activity.query.filter_by(name=migration_name).first()
    
    if not activity:
        print(f"Creating system activity: '{migration_name}'...")
        activity = Activity(
            name=migration_name,
            description="System generated activity for initial data import.",
            default_points=0,
            active=True 
        )
        db.session.add(activity)
        db.session.commit()
    
    return activity

def import_students(filename="students.csv"):
    if not os.path.exists(filename):
        print(f"Error: File {filename} not found.")
        return

    print(f"--- Starting Student Import from {filename} ---")
    
    # 1. Get the Activity ID for the audit trail
    migration_activity = get_or_create_migration_activity()
    
    # 2. Get an Admin user for the 'recorded_by' field (Audit Trail)
    admin_user = User.query.filter_by(role='admin').first()
    if not admin_user:
        admin_user = User.query.first()
        if not admin_user:
            print("Error: No users found in system. Please create an admin user first.")
            return

    count_new = 0
    count_skipped = 0
    
    with open(filename, 'r', encoding='utf-8-sig') as f: 
        reader = csv.DictReader(f)
        
        required_headers = ['Full Name', 'Initial Points']
        if not all(h in reader.fieldnames for h in required_headers):
            print(f"Error: CSV missing required columns.")
            print(f"Expected: {required_headers}")
            return

        for row in reader:
            name = row['Full Name'].strip()
            
            try:
                points_str = row['Initial Points'].strip()
                points = int(points_str) if points_str else 0
            except ValueError:
                print(f"Warning: Invalid points for '{name}'. Defaulting to 0.")
                points = 0
            
            existing = Student.query.filter_by(full_name=name).first()
            if existing:
                print(f"Skipping '{name}' (Already exists)")
                count_skipped += 1
                continue

            new_student = Student(
                full_name=name,
                balance=0,
                active=True
            )
            db.session.add(new_student)
            db.session.flush()

            if points > 0:
                trans = Transaction(
                    student_id=new_student.id,
                    activity_id=migration_activity.id,
                    points=points,
                    description="Initial Balance Import",
                    user_id=admin_user.id,
                    timestamp=datetime.utcnow()
                )
                db.session.add(trans)
                new_student.balance = points
            
            count_new += 1
            print(f"Imported: {name} (Points: {points})")

    db.session.commit()
    print(f"\n--- Student Import Complete ---")
    print(f"New Students: {count_new}")
    print(f"Skipped:      {count_skipped}")

def import_prizes(filename="prizes.csv"):
    if not os.path.exists(filename):
        print(f"Error: File {filename} not found.")
        return

    print(f"--- Starting Prize Import from {filename} ---")

    count_new = 0
    count_skipped = 0
    
    with open(filename, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        required_headers = ['Prize Name', 'Cost', 'Stock']
        if not all(h in reader.fieldnames for h in required_headers):
            print(f"Error: CSV missing required columns.")
            print(f"Expected: {required_headers}")
            return

        for row in reader:
            name = row['Prize Name'].strip()
            
            # Parse Cost
            try:
                cost_str = row['Cost'].strip()
                cost = int(cost_str) if cost_str else 0
            except ValueError:
                print(f"Warning: Invalid cost for '{name}'. Defaulting to 0.")
                cost = 0

            # Parse Stock
            try:
                stock_str = row['Stock'].strip()
                stock = int(stock_str) if stock_str else 0
            except ValueError:
                print(f"Warning: Invalid stock for '{name}'. Defaulting to 0.")
                stock = 0
            
            # Check for existing prize
            existing = Prize.query.filter_by(name=name).first()
            if existing:
                print(f"Skipping '{name}' (Already exists)")
                count_skipped += 1
                continue

            # Create Prize
            new_prize = Prize(
                name=name,
                cost=cost,
                stock=stock,
                image_file='default_prize.png', # Default image for imported items
                active=True
            )
            db.session.add(new_prize)
            
            count_new += 1
            print(f"Imported: {name} (Cost: {cost}, Stock: {stock})")

    db.session.commit()
    print(f"\n--- Prize Import Complete ---")
    print(f"New Prizes:   {count_new}")
    print(f"Skipped:      {count_skipped}")

if __name__ == "__main__":
    with app.app_context():
        print("\n=== SYSTEM IMPORT UTILITY ===")
        print("1. Import Students (students.csv)")
        print("2. Import Prizes (prizes.csv)")
        print("3. Exit")
        
        choice = input("\nSelect option: ")
        
        if choice == "1":
            import_students()
        elif choice == "2":
            import_prizes()
        elif choice == "3":
            print("Exiting.")
        else:
            print("Invalid selection")