"""
migrate_step2.py
Migration script for Step 2:
1. Verifies no duplicate (category, category_id_seq) exists.
2. Adds channel_chat_id and category_chat_id columns to items table (for safe old-brand to new-brand transition).
3. Backfills existing posted items with their legacy channel handles so they remain editable/markable as SOLD.
4. Creates a UNIQUE index on (category, category_id_seq) where category_id_seq IS NOT NULL.
"""
import sqlite3
import os
import sys

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB_PATH = "betedires.db"

LEGACY_CATEGORY_CHANNELS = {
    "Electronics": "@gondergebeyaelec",
    "Clothing": "@gondergebeyaclothe",
    "Furniture": "@gondergebeyafurniture",
    "House/Rent": "@gondergebeyabet",
    "Vehicles": "@gondergebeyamekina",
    "Others": "@Gondergebeya1"
}
LEGACY_MAIN_CHANNEL = "@Gondergebeya1"

def run_migration():
    print("=== STARTING STEP 2 DATABASE MIGRATION ===")
    print(f"Target Database: {DB_PATH}\n")
    
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database file {DB_PATH} not found!")
        sys.exit(1)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Detect duplicates before applying UNIQUE constraint
    print("Step 1: Checking for duplicate serials...")
    cursor.execute("""
        SELECT category, category_id_seq, COUNT(*) 
        FROM items 
        WHERE category_id_seq IS NOT NULL 
        GROUP BY category, category_id_seq 
        HAVING COUNT(*) > 1
    """)
    duplicates = cursor.fetchall()
    if duplicates:
        print(f"ABORTING MIGRATION: Found {len(duplicates)} duplicate serial combinations:")
        for cat, seq, count in duplicates:
            print(f"  Category: {cat}, Sequence: {seq} (Count: {count})")
        conn.close()
        sys.exit(1)
    print("  -> Passed. No duplicate serials found.")

    # 2. Add columns channel_chat_id and category_chat_id if not present
    print("\nStep 2: Adding channel_chat_id and category_chat_id columns...")
    cursor.execute("PRAGMA table_info(items)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "channel_chat_id" not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN channel_chat_id TEXT")
        print("  -> Added channel_chat_id column.")
    else:
        print("  -> channel_chat_id column already exists.")
        
    if "category_chat_id" not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN category_chat_id TEXT")
        print("  -> Added category_chat_id column.")
    else:
        print("  -> category_chat_id column already exists.")

    # 3. Backfill legacy items with their respective channels so they remain editable/markable as SOLD
    print("\nStep 3: Backfilling legacy channel handles for existing POSTED / SOLD items...")
    cursor.execute("SELECT id, category, channel_message_id, category_message_id, channel_chat_id, category_chat_id FROM items WHERE UPPER(status) IN ('POSTED', 'SOLD')")
    legacy_items = cursor.fetchall()
    backfilled_count = 0
    for it_id, cat, main_msg, cat_msg, cur_main_chat, cur_cat_chat in legacy_items:
        new_main_chat = cur_main_chat or LEGACY_MAIN_CHANNEL
        new_cat_chat = cur_cat_chat or LEGACY_CATEGORY_CHANNELS.get(cat, LEGACY_MAIN_CHANNEL)
        cursor.execute(
            "UPDATE items SET channel_chat_id = ?, category_chat_id = ? WHERE id = ?",
            (new_main_chat, new_cat_chat, it_id)
        )
        backfilled_count += 1
    print(f"  -> Backfilled {backfilled_count} legacy items.")

    # 4. Create UNIQUE index
    print("\nStep 4: Creating UNIQUE index on (category, category_id_seq)...")
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_item_category_seq 
        ON items(category, category_id_seq) 
        WHERE category_id_seq IS NOT NULL
    """)
    print("  -> Unique index 'uq_item_category_seq' created successfully.")

    conn.commit()
    conn.close()
    print("\n=== STEP 2 MIGRATION COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_migration()
