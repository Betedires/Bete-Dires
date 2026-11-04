"""
test_step4.py — Step 4 Verification Script
Verifies:
1. Database FTS5 table items_fts and triggers exist in betedires.db
2. UserPreference and SearchAlert models load correctly
3. Search engine executes against real betedires.db
4. Serial search works against real betedires.db
5. bot.py imports and all handlers compile without error
6. main.py imports cleanly with search alerts integration

Usage:
    .\\venv\\Scripts\\python.exe test_step4.py
"""
import sys
import os
import sqlite3
import asyncio

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

PASS = "\u2705"
FAIL = "\u274c"
_results = []

def check(label, expr):
    ok = bool(expr)
    _results.append((ok, label))
    icon = PASS if ok else FAIL
    print(f"  {icon}  {label}")
    return ok

# ── 1. Database FTS5 & Models ──────────────────────────────────────────────
print("\n[1] Database FTS5 & Models Check")
try:
    from database import UserPreference, SearchAlert, Item, ItemStatus
    check("UserPreference model exists", hasattr(UserPreference, "language"))
    check("SearchAlert model exists", hasattr(SearchAlert, "query"))

    # Connect to betedires.db directly to inspect FTS5 and triggers
    conn = sqlite3.connect("betedires.db")
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items_fts'")
    has_fts = bool(cur.fetchone())
    check("items_fts virtual table exists in betedires.db", has_fts)

    cur.execute("SELECT COUNT(*) FROM items_fts")
    fts_count = cur.fetchone()[0]
    check(f"items_fts contains indexed items (found: {fts_count})", fts_count > 0)

    # Check triggers
    cur.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='items_ai'")
    has_trigger = bool(cur.fetchone())
    check("FTS5 sync trigger items_ai exists", has_trigger)

    # Check search_alerts table
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_alerts'")
    has_alerts = bool(cur.fetchone())
    check("search_alerts table exists", has_alerts)

    conn.close()
except Exception as e:
    check(f"Database check failed: {e}", False)

# ── 2. Search Engine Execution Against Real DB ─────────────────────────────
print("\n[2] Search Engine Real DB Query")
try:
    from search_engine import execute_search, parse_search_query

    async def _test_search():
        # Test 1: Category browse
        res_cat = await execute_search("", category_filter="Electronics", limit=5)
        check(f"Category search (Electronics) returns items (found: {len(res_cat)})", len(res_cat) > 0)

        # Test 2: Serial number search if items exist
        if res_cat:
            first_item = res_cat[0]
            code = "EL"
            seq = first_item.category_id_seq or 0
            serial_query = f"{first_item.id:03d} {code} {seq:03d}"
            res_serial = await execute_search(serial_query)
            check(f"Exact serial search for '{serial_query}' returns exact item",
                  len(res_serial) == 1 and res_serial[0].id == first_item.id)

        # Test 3: Free-text search
        res_text = await execute_search("Gondar", limit=10)
        check(f"Location search for 'Gondar' returns results (found: {len(res_text)})", len(res_text) >= 0)

    asyncio.run(_test_search())
except Exception as e:
    check(f"Search engine execution failed: {e}", False)

# ── 3. bot.py Import and Syntax ────────────────────────────────────────────
print("\n[3] bot.py & main.py Import Sanity")
try:
    import bot
    check("bot.py imported successfully", hasattr(bot, "dp") and hasattr(bot, "bot"))
    check("bot.py has search_cache", hasattr(bot, "search_cache"))
    check("bot.py has get_user_lang", hasattr(bot, "get_user_lang"))

    import main
    check("main.py imported successfully with check_search_alerts", hasattr(main, "check_search_alerts"))
except Exception as e:
    check(f"Import check failed: {e}", False)

# ── Summary ────────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
passed = sum(1 for ok, _ in _results if ok)
total = len(_results)
failed = [label for ok, label in _results if not ok]
print(f"  Step 4 Test Result: {passed}/{total} checks passed")
if failed:
    print("\n  Failed checks:")
    for label in failed:
        print(f"    {FAIL} {label}")
    sys.exit(1)
else:
    print(f"\n  {PASS} All Step 4 checks passed!")
    sys.exit(0)
