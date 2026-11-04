"""
backup.py — Standalone CLI & Cron SQLite Backup Tool
Bete Dires (ቤተ ድረስ) Marketplace

Usage:
    python backup.py
    python backup.py --keep 30

Features:
- Online SQLite backup API (zero downtime, safe while server is actively running).
- Rotates backups keeping the newest N copies (default: 14).
- Safe exit codes for automated cron jobs or systemd timers.
"""

import os
import sys
import argparse
import sqlite3
from datetime import datetime

def backup_database(db_path: str = "betedires.db", backup_dir: str = "backups", keep_count: int = 14) -> str:
    if not os.path.exists(db_path):
        print(f"Error: Source database '{db_path}' not found.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"betedires_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)

    print(f"Backing up '{db_path}' -> '{backup_path}'...")
    src_conn = sqlite3.connect(db_path)
    dst_conn = sqlite3.connect(backup_path)
    try:
        with dst_conn:
            src_conn.backup(dst_conn)
    finally:
        src_conn.close()
        dst_conn.close()

    size_kb = round(os.path.getsize(backup_path) / 1024, 1)
    print(f"Backup created successfully: {backup_filename} ({size_kb} KB)")

    # Verify backup integrity
    v_conn = sqlite3.connect(backup_path)
    try:
        check = v_conn.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            print(f"Warning: Integrity check returned: {check}", file=sys.stderr)
        else:
            print("Integrity check: OK")
        item_count = v_conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        print(f"Verified items in backup: {item_count}")
    finally:
        v_conn.close()

    # Rotation: keep newest N backups
    all_backups = sorted([
        os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
        if f.startswith("betedires_backup_") and f.endswith(".db")
    ], key=os.path.getmtime, reverse=True)

    if len(all_backups) > keep_count:
        print(f"Rotating old backups (retaining newest {keep_count})...")
        for old in all_backups[keep_count:]:
            try:
                os.remove(old)
                print(f"  Removed: {os.path.basename(old)}")
            except Exception as e:
                print(f"  Could not remove {old}: {e}", file=sys.stderr)

    return backup_path

def main():
    parser = argparse.ArgumentParser(description="Create SQLite snapshot backup for Bete Dires Marketplace")
    parser.add_argument("--db", default="betedires.db", help="Path to SQLite database file")
    parser.add_argument("--dir", default="backups", help="Directory to store backup files")
    parser.add_argument("--keep", type=int, default=14, help="Number of recent backups to retain")
    args = parser.parse_args()

    backup_database(db_path=args.db, backup_dir=args.dir, keep_count=args.keep)

if __name__ == "__main__":
    main()
