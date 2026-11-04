"""
restore.py — Standalone CLI Restore Tool for SQLite Database
Bete Dires (ቤተ ድረስ) Marketplace

Usage:
    python restore.py --latest
    python restore.py --from backups/betedires_backup_20261014_160713.db

Features:
- Takes a safety pre-restore backup of the target database before replacing it.
- Verifies integrity of the backup file before restoring.
- Reconnects and confirms table structure and row counts after restore.
"""

import os
import sys
import shutil
import argparse
import sqlite3
from datetime import datetime

def restore_database(source_file: str, target_db: str = "betedires.db"):
    if not os.path.exists(source_file):
        print(f"Error: Source backup file '{source_file}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"1. Verifying integrity of '{source_file}'...")
    src_conn = sqlite3.connect(source_file)
    try:
        check = src_conn.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            print(f"Error: Integrity check failed on backup: {check}", file=sys.stderr)
            sys.exit(1)
        item_count = src_conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        print(f"   Integrity check: OK. Items to restore: {item_count}")
    finally:
        src_conn.close()

    # Safety snapshot of current target_db if it exists
    if os.path.exists(target_db):
        safety_path = f"{target_db}.pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"2. Creating safety copy of current '{target_db}' -> '{safety_path}'...")
        shutil.copy2(target_db, safety_path)

    # Perform restoration using SQLite backup API
    print(f"3. Restoring '{source_file}' -> '{target_db}'...")
    src_conn = sqlite3.connect(source_file)
    dst_conn = sqlite3.connect(target_db)
    try:
        with dst_conn:
            src_conn.backup(dst_conn)
    finally:
        src_conn.close()
        dst_conn.close()

    # Verify restored target
    verify_conn = sqlite3.connect(target_db)
    try:
        v_check = verify_conn.execute("PRAGMA integrity_check").fetchone()[0]
        v_count = verify_conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        print(f"4. Restore successful! Integrity: {v_check}. Active items: {v_count}")
    finally:
        verify_conn.close()

def main():
    parser = argparse.ArgumentParser(description="Restore Bete Dires SQLite database from backup")
    parser.add_argument("--from-file", dest="from_file", help="Path to backup database file")
    parser.add_argument("--latest", action="store_true", help="Automatically restore from the latest backup in backups/")
    parser.add_argument("--target", default="betedires.db", help="Target database path (default: betedires.db)")
    args = parser.parse_args()

    if args.latest:
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            print(f"Error: Directory '{backup_dir}' not found.", file=sys.stderr)
            sys.exit(1)
        candidates = sorted([
            os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
            if f.endswith(".db")
        ], key=os.path.getmtime, reverse=True)
        if not candidates:
            print(f"Error: No backup files found in '{backup_dir}'.", file=sys.stderr)
            sys.exit(1)
        source = candidates[0]
        print(f"Selected latest backup: {source}")
    elif args.from_file:
        source = args.from_file
    else:
        print("Error: Specify either --from-file <path> or --latest", file=sys.stderr)
        sys.exit(1)

    restore_database(source, target_db=args.target)

if __name__ == "__main__":
    main()
