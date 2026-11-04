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
    backup_path = os.path.join(backup_dir, "betedires_pre_step3_backup.db")

    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        sys.exit(1)

    print(f"1. Backing up '{db_path}' to '{backup_path}'...")
    shutil.copy2(db_path, backup_path)
    print("   Backup created successfully.")

    print(f"2. Connecting to '{db_path}' for schema migration...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(items)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    print(f"   Existing columns in 'items': {len(existing_cols)} columns found.")

    if "post_error" not in existing_cols:
        print("   Adding column 'post_error' (TEXT)...")
        cursor.execute("ALTER TABLE items ADD COLUMN post_error TEXT NULL")
        conn.commit()
        print("   Column 'post_error' added successfully.")
    else:
        print("   Column 'post_error' already exists.")

    # Verify
    cursor.execute("PRAGMA table_info(items)")
    updated_cols = [row[1] for row in cursor.fetchall()]
    print(f"   Updated column list: {updated_cols}")
    assert "post_error" in updated_cols, "Verification failed: post_error not found"

    conn.close()
    print("Step 3 Database Migration completed successfully!")

if __name__ == "__main__":
    main()
