import os
import sys
import sqlite3
import asyncio

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FWD_DIR = os.path.join(BASE_DIR, "telegram_forwarder")
for p in [BASE_DIR, FWD_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from id_manager import format_serial, ITEM_SHORTHANDS, get_next_category_sequence

PASS = "\u2705"
FAIL = "\u274c"
_results = []

def check(label, expr):
    ok = bool(expr)
    _results.append((ok, label))
    icon = PASS if ok else FAIL
    print(f"  {icon}  {label}")
    return ok

def run_tests():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("\n=== Testing id_manager.py ===")

    # 1. Format Serial for all categories
    check("format_serial: Electronics", format_serial(50, "Electronics", 15) == "050 EL 015")
    check("format_serial: Cosmetics", format_serial(62, "Cosmetics", 1) == "062 CO 001")
    check("format_serial: Vehicles", format_serial(1, "Vehicles", 1) == "001 VE 001")
    check("format_serial: Furniture", format_serial(43, "Furniture", 14) == "043 FU 014")
    check("format_serial: Clothing", format_serial(999, "Clothing", 99) == "999 CL 099")
    check("format_serial: House/Rent", format_serial(7, "House/Rent", 3) == "007 HR 003")
    check("format_serial: Others", format_serial(100, "Others", 12) == "100 OT 012")
    check("format_serial: Unknown defaults to OT", format_serial(100, "UnknownCategory", 12) == "100 OT 012")

    # 2. In-memory DB sequence calculation test
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE items (
        id INTEGER PRIMARY KEY,
        category TEXT,
        category_id_seq INTEGER,
        UNIQUE (category, category_id_seq)
    )""")

    def next_seq_for(cat):
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(category_id_seq), 0) + 1 FROM items WHERE category = ?", (cat,))
        return cur.fetchone()[0]

    seq1 = next_seq_for("Cosmetics")
    check("Initial sequence is 1 for empty category", seq1 == 1)

    conn.execute("INSERT INTO items (id, category, category_id_seq) VALUES (1, 'Cosmetics', 1)")
    conn.commit()

    seq2 = next_seq_for("Cosmetics")
    check("Sequence increments to 2 after inserting item", seq2 == 2)

    seq_el = next_seq_for("Electronics")
    check("Separate category has independent sequence starting at 1", seq_el == 1)

    # 3. Test uniqueness constraint prevents duplicates
    duplicate_failed = False
    try:
        conn.execute("INSERT INTO items (id, category, category_id_seq) VALUES (2, 'Cosmetics', 1)")
        conn.commit()
    except sqlite3.IntegrityError:
        duplicate_failed = True

    check("UNIQUE constraint prevents duplicate (category, category_id_seq)", duplicate_failed)
    conn.close()

    # 4. Check that last_id.txt is NOT generated or depended on
    last_id_path = os.path.join(FWD_DIR, "last_id.txt")
    if os.path.exists(last_id_path):
        os.remove(last_id_path)
    from id_manager import get_next_id_sync
    _, _, serial = get_next_id_sync("Electronics", db_path="betedires.db")
    check("get_next_id_sync generates serial from real DB", len(serial.split()) == 3)
    check("last_id.txt is not created during serial generation", not os.path.exists(last_id_path))

    print("\n" + "=" * 55)
    passed = sum(1 for ok, _ in _results if ok)
    total = len(_results)
    print(f"ID Manager Tests: {passed}/{total} passed.")
    if passed != total:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
