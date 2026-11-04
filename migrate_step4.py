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
    backup_path = os.path.join(backup_dir, "betedires_pre_step4_backup.db")

    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        sys.exit(1)

    print(f"1. Backing up '{db_path}' to '{backup_path}'...")
    shutil.copy2(db_path, backup_path)
    print("   Backup created successfully.")

    print(f"2. Connecting to '{db_path}' for Step 4 migration...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Step A: Create items_fts FTS5 table
    print("   Creating items_fts full-text search table...")
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
            item_id UNINDEXED,
            name,
            price,
            location,
            condition,
            category,
            serial,
            tokenize='unicode61'
        );
    """)

    # Step B: Create automatic synchronization triggers
    print("   Creating automatic sync triggers for FTS5...")
    cursor.execute("DROP TRIGGER IF EXISTS items_ai")
    cursor.execute("""
        CREATE TRIGGER items_ai AFTER INSERT ON items BEGIN
            INSERT INTO items_fts(item_id, name, price, location, condition, category, serial)
            VALUES (
                new.id,
                coalesce(new.name, ''),
                coalesce(new.price, ''),
                coalesce(new.location, ''),
                coalesce(new.condition, ''),
                coalesce(new.category, 'Others'),
                printf('%03d', new.id) || ' ' || coalesce(new.category, 'OT') || ' ' || printf('%03d', coalesce(new.category_id_seq, 0))
            );
        END;
    """)

    cursor.execute("DROP TRIGGER IF EXISTS items_ad")
    cursor.execute("""
        CREATE TRIGGER items_ad AFTER DELETE ON items BEGIN
            DELETE FROM items_fts WHERE item_id = old.id;
        END;
    """)

    cursor.execute("DROP TRIGGER IF EXISTS items_au")
    cursor.execute("""
        CREATE TRIGGER items_au AFTER UPDATE ON items BEGIN
            DELETE FROM items_fts WHERE item_id = old.id;
            INSERT INTO items_fts(item_id, name, price, location, condition, category, serial)
            VALUES (
                new.id,
                coalesce(new.name, ''),
                coalesce(new.price, ''),
                coalesce(new.location, ''),
                coalesce(new.condition, ''),
                coalesce(new.category, 'Others'),
                printf('%03d', new.id) || ' ' || coalesce(new.category, 'OT') || ' ' || printf('%03d', coalesce(new.category_id_seq, 0))
            );
        END;
    """)

    # Step C: Populate items_fts with existing items
    print("   Indexing existing items into items_fts...")
    cursor.execute("DELETE FROM items_fts")
    cursor.execute("""
        INSERT INTO items_fts(item_id, name, price, location, condition, category, serial)
        SELECT 
            id,
            coalesce(name, ''),
            coalesce(price, ''),
            coalesce(location, ''),
            coalesce(condition, ''),
            coalesce(category, 'Others'),
            printf('%03d', id) || ' ' || coalesce(category, 'OT') || ' ' || printf('%03d', coalesce(category_id_seq, 0))
        FROM items;
    """)
    fts_count = cursor.execute("SELECT COUNT(*) FROM items_fts").fetchone()[0]
    print(f"   Indexed {fts_count} existing items into items_fts.")

    # Step D: Create user_preferences table for bilingual setting
    print("   Creating user_preferences table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'am',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Step E: Create search_alerts table for "Notify Me" saved alerts
    print("   Creating search_alerts table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            query TEXT NOT NULL,
            normalized_query TEXT NOT NULL,
            category TEXT,
            max_price REAL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_search_alerts_user_id ON search_alerts(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_search_alerts_is_active ON search_alerts(is_active);")

    conn.commit()
    conn.close()
    print("Step 4 Database Migration completed successfully!")

if __name__ == "__main__":
    main()
