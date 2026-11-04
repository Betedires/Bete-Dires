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
    backup_path = os.path.join(backup_dir, "betedires_pre_forwarder_backup.db")

    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        sys.exit(1)

    print(f"1. Backing up '{db_path}' to '{backup_path}'...")
    shutil.copy2(db_path, backup_path)
    print("   Backup created successfully.")

    print(f"2. Connecting to '{db_path}' for forwarder schema migration...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(items)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    print(f"   Existing columns in 'items': {len(existing_cols)} columns found.")

    new_columns = [
        ("source_chat_id", "TEXT NULL"),
        ("source_message_id", "INTEGER NULL"),
        ("source_link", "TEXT NULL"),
        ("content_hash", "TEXT NULL"),
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing_cols:
            print(f"   Adding column '{col_name}' ({col_type})...")
            cursor.execute(f"ALTER TABLE items ADD COLUMN {col_name} {col_type}")
            print(f"   Column '{col_name}' added.")
        else:
            print(f"   Column '{col_name}' already exists.")

    cursor.execute("CREATE INDEX IF NOT EXISTS ix_items_content_hash ON items (content_hash)")
    conn.commit()
    print("   Index 'ix_items_content_hash' created/verified.")

    # Verify
    cursor.execute("PRAGMA table_info(items)")
    updated_cols = [row[1] for row in cursor.fetchall()]
    for col_name, _ in new_columns:
        assert col_name in updated_cols, f"Verification failed: {col_name} not found"

    conn.close()
    print("Forwarder Database Migration completed successfully!")

if __name__ == "__main__":
    main()
