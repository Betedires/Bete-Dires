"""
audit_out_of_sync.py
Read-only diagnostic script to inspect:
1. Duplicate serial numbers (category, category_id_seq)
2. Live posts where category_message_id or channel_message_id is missing
Does NOT modify any data.
"""
import sqlite3
import os
import sys

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB_PATH = "betedires.db" if os.path.exists("betedires.db") else "gonder_gebeya.db"

def run_audit():
    print(f"=== BETE DIRES (ቤተ ድረስ) READ-ONLY DATABASE AUDIT ===")
    print(f"Database: {DB_PATH}\n")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check total items and counts by status
    cursor.execute("SELECT status, count(*) FROM items GROUP BY status")
    status_counts = cursor.fetchall()
    print("--- Item Counts by Status ---")
    for status, count in status_counts:
        print(f"  {status}: {count}")
        
    cursor.execute("SELECT category, count(*) FROM items GROUP BY category")
    cat_counts = cursor.fetchall()
    print("\n--- Item Counts by Category ---")
    for cat, count in cat_counts:
        print(f"  {cat}: {count}")

    # 1. Check for Duplicate Serials
    print("\n--- 1. Duplicate Serial Check ---")
    cursor.execute("""
        SELECT category, category_id_seq, COUNT(*) 
        FROM items 
        WHERE category_id_seq IS NOT NULL 
        GROUP BY category, category_id_seq 
        HAVING COUNT(*) > 1
    """)
    duplicates = cursor.fetchall()
    if duplicates:
        print(f"⚠️ FOUND {len(duplicates)} DUPLICATE SERIAL COMBINATION(S):")
        for cat, seq, count in duplicates:
            print(f"  Category: {cat}, Sequence: {seq} -> {count} items share this sequence!")
            cursor.execute("SELECT id, name, status, created_at FROM items WHERE category = ? AND category_id_seq = ?", (cat, seq))
            for item in cursor.fetchall():
                print(f"    Item ID: {item[0]} | Name: {item[1]} | Status: {item[2]} | Created: {item[3]}")
    else:
        print("✅ No duplicate (category, category_id_seq) serials detected.")

    # 2. Check for Missing Category / Channel Message IDs on POSTED or SOLD items
    print("\n--- 2. Out-of-Sync Live Posts Check (Missing category_message_id) ---")
    cursor.execute("""
        SELECT id, name, category, category_id_seq, status, channel_message_id, category_message_id, created_at
        FROM items
        WHERE status IN ('posted', 'sold') AND (category_message_id IS NULL OR channel_message_id IS NULL)
        ORDER BY id DESC
    """)
    out_of_sync = cursor.fetchall()
    if out_of_sync:
        print(f"⚠️ FOUND {len(out_of_sync)} POSTED/SOLD ITEM(S) WITH MISSING MESSAGE ID(S):")
        print(f"{'ID':<6} | {'Serial/Category':<20} | {'Status':<8} | {'Main Msg':<10} | {'Cat Msg':<10} | {'Item Name'}")
        print("-" * 80)
        for row in out_of_sync:
            cat_seq = f"{row[2]} #{row[3]}"
            main_m = str(row[5]) if row[5] is not None else "MISSING"
            cat_m = str(row[6]) if row[6] is not None else "MISSING"
            print(f"{row[0]:<6} | {cat_seq:<20} | {row[4]:<8} | {main_m:<10} | {cat_m:<10} | {row[1]}")
    else:
        print("✅ All POSTED and SOLD items have both main and category message IDs.")

    conn.close()
    print("\nAudit completed safely. No changes made.")

if __name__ == "__main__":
    run_audit()
