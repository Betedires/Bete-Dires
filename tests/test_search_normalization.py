import os
import sys
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from search_engine import (
    normalize_price_str,
    parse_price_number,
    is_serial_number,
    parse_search_query,
    CITY_SYNONYMS,
    CATEGORY_SYNONYMS,
    TERM_SYNONYMS
)

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

    print("\n=== Testing search_normalization.py ===")

    # 1. Price Multipliers Normalization
    check("normalize_price_str: 20 ሺ -> 20000", normalize_price_str("20 ሺ") == "20000")
    check("normalize_price_str: 20 ሺህ -> 20000", normalize_price_str("20 ሺህ") == "20000")
    check("normalize_price_str: 25k -> 25000", normalize_price_str("25k") == "25000")
    check("normalize_price_str: 15 thousand -> 15000", normalize_price_str("15 thousand") == "15000")

    # 2. Numeric Price Parser
    check("parse_price_number: 20,000 ብር -> 20000.0", parse_price_number("20,000 ብር") == 20000.0)
    check("parse_price_number: 15 ሺ -> 15000.0", parse_price_number("15 ሺ") == 15000.0)
    check("parse_price_number: invalid string -> None", parse_price_number("N/A") is None)

    # 3. Serial Number Recognition
    ok, s1 = is_serial_number("050 EL 015")
    check("is_serial_number: standard 050 EL 015 recognized", ok and s1 == "050 EL 015")

    ok, s2 = is_serial_number("043 FU 14")
    check("is_serial_number: 043 FU 14 formats to 043 FU 014", ok and s2 == "043 FU 014")

    ok, s3 = is_serial_number("062 CO 1")
    check("is_serial_number: 062 CO 1 formats to 062 CO 001", ok and s3 == "062 CO 001")

    ok, s4 = is_serial_number("050")
    check("is_serial_number: standalone global id 050 recognized", ok and s4 == "050")

    ok, _ = is_serial_number("iphone 12 20000")
    check("is_serial_number: free-text query NOT treated as serial", not ok)

    # 4. City Normalization (Amharic & English variants)
    for variant in ["gondar", "gonder", "ጎንደር", "ጐንደር"]:
        check(f"CITY_SYNONYMS: {variant} -> Gondar", CITY_SYNONYMS.get(variant) == "Gondar")

    for variant in ["bahirdar", "bahir dar", "ባህር ዳር", "ባህርዳር", "ባ/ዳር"]:
        check(f"CITY_SYNONYMS: {variant} -> Bahirdar", CITY_SYNONYMS.get(variant) == "Bahirdar")

    for variant in ["addis ababa", "addis", "አዲስ አበባ", "አዲስአበባ"]:
        check(f"CITY_SYNONYMS: {variant} -> Addis Ababa", CITY_SYNONYMS.get(variant) == "Addis Ababa")

    # 5. Free-Text Search Parsing: "iphone xr 20000 Gondar"
    q1 = parse_search_query("iphone xr 20000 Gondar")
    check("parse_search_query: location extracted as Gondar", q1.location == "Gondar")
    check("parse_search_query: max_price extracted as 20000", q1.max_price == 20000.0)
    check("parse_search_query: category extracted as Electronics", q1.category == "Electronics")
    check("parse_search_query: keywords include iphone and xr", "iphone" in q1.keywords and "xr" in q1.keywords)
    check("parse_search_query: expanded_terms includes Amharic 'አይፎን'", "አይፎን" in q1.expanded_terms)

    # 6. Free-Text Search Parsing: "ሶፋ 15 ሺ ጎንደር"
    q2 = parse_search_query("ሶፋ 15 ሺ ጎንደር")
    check("parse_search_query: Amharic 15 ሺ parsed as max_price 15000", q2.max_price == 15000.0)
    check("parse_search_query: Amharic ጎንደር parsed as location Gondar", q2.location == "Gondar")
    check("parse_search_query: category extracted as Furniture", q2.category == "Furniture")
    check("parse_search_query: expanded_terms includes English 'sofa'", "sofa" in q2.expanded_terms)

    # 7. In-memory FTS5 Query Test with bilingual matching
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE VIRTUAL TABLE items_fts USING fts5(
        item_id UNINDEXED, name, price, location, condition, category, serial, tokenize='unicode61'
    )""")
    conn.execute("""INSERT INTO items_fts VALUES (
        1, 'iPhone 13 Pro Max 256GB', '65,000', '(Gondar) Arada', 'ያገለገለ', 'Electronics', '050 EL 015'
    )""")
    conn.execute("""INSERT INTO items_fts VALUES (
        2, 'የሳሎን ሶፋ አዲስ', '18,000', '(Bahirdar) Kebele 4', 'አዲስ', 'Furniture', '043 FU 014'
    )""")
    conn.commit()

    # Search with English 'iphone'
    rows_en = conn.execute("SELECT item_id FROM items_fts WHERE items_fts MATCH ?", ('iphone*',)).fetchall()
    check("FTS5 query: matches English 'iphone'", len(rows_en) == 1 and int(rows_en[0][0]) == 1)

    # Search with Amharic 'ሶፋ'
    rows_am = conn.execute("SELECT item_id FROM items_fts WHERE items_fts MATCH ?", ('ሶፋ*',)).fetchall()
    check("FTS5 query: matches Amharic 'ሶፋ'", len(rows_am) == 1 and int(rows_am[0][0]) == 2)

    # Search by serial number
    rows_serial = conn.execute("SELECT item_id FROM items_fts WHERE items_fts MATCH ?", ('"050 EL 015"',)).fetchall()
    check("FTS5 query: matches serial '050 EL 015'", len(rows_serial) == 1 and int(rows_serial[0][0]) == 1)
    conn.close()

    print("\n" + "=" * 55)
    passed = sum(1 for ok, _ in _results if ok)
    total = len(_results)
    print(f"Search Normalization Tests: {passed}/{total} passed.")
    if passed != total:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
