import os
import shutil
import sqlite3
import sys

def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    db_path = "betedires.db"
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, "betedires_pre_step5_backup.db")

    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        sys.exit(1)

    print(f"1. Backing up '{db_path}' to '{backup_path}'...")
    shutil.copy2(db_path, backup_path)
    print("   Backup created successfully.")

    print(f"2. Connecting to '{db_path}' for Step 5 migration...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Step A: Add columns to items table
    cursor.execute("PRAGMA table_info(items)")
    existing_cols = [row[1] for row in cursor.fetchall()]

    new_cols = [
        ("telegram_user_id", "INTEGER NULL"),
        ("is_verified", "INTEGER DEFAULT 0"),
        ("expiry_warning_sent", "INTEGER DEFAULT 0")
    ]

    for col_name, col_def in new_cols:
        if col_name not in existing_cols:
            print(f"   Adding column '{col_name}' ({col_def}) to items...")
            cursor.execute(f"ALTER TABLE items ADD COLUMN {col_name} {col_def}")
        else:
            print(f"   Column '{col_name}' already exists in items.")

    cursor.execute("CREATE INDEX IF NOT EXISTS ix_items_telegram_user_id ON items(telegram_user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_items_is_verified ON items(is_verified)")

    # Step B: Create sellers table
    print("   Creating 'sellers' table for seller verification...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sellers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id INTEGER UNIQUE,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            username TEXT,
            id_photo_path TEXT,
            status TEXT DEFAULT 'pending',
            rejection_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_sellers_telegram_user_id ON sellers(telegram_user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_sellers_status ON sellers(status)")

    # Step C: Create reports table
    print("   Creating 'reports' table for listing reporting...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            reporter_user_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_reports_item_id ON reports(item_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_reports_status ON reports(status)")

    conn.commit()
    conn.close()

    # Step D: Ensure private secure directory exists
    os.makedirs(os.path.join("secure_uploads", "ids"), exist_ok=True)
    print("   Created secure_uploads/ids/ directory.")

    print("Step 5 Database Migration completed successfully!")

if __name__ == "__main__":
    main()
