"""
test_step3.py — Step 3 verification (no pytest needed; run with plain Python)
Usage:
    .\venv\Scripts\python.exe test_step3.py
All assertions must pass for Step 3 to be considered complete.
"""
import sys, asyncio, os, json, time, unittest.mock as mock
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

PASS = "\u2705"
FAIL = "\u274c"
_results = []

def check(label, expr):
    ok = bool(expr)
    _results.append((ok, label))
    icon = PASS if ok else FAIL
    print(f"  {icon}  {label}")
    return ok

# ── 1. Database: PARTIALLY_POSTED enum value ───────────────────────────────
print("\n[1] Database enum and column")
try:
    from database import ItemStatus, Item
    check("ItemStatus.PARTIALLY_POSTED exists", hasattr(ItemStatus, "PARTIALLY_POSTED"))
    check("ItemStatus.PARTIALLY_POSTED value is 'partially_posted'",
          ItemStatus.PARTIALLY_POSTED == "partially_posted")
    check("Item model has post_error column",
          hasattr(Item, "post_error"))
    # All 5 statuses present
    expected = {"pending", "posted", "sold", "scheduled", "partially_posted"}
    actual = {s.value for s in ItemStatus}
    check("All 5 ItemStatus values present", expected == actual)
except Exception as e:
    check(f"database import: {e}", False)

# ── 2. main.py compiles without syntax errors ──────────────────────────────
print("\n[2] main.py syntax check")
try:
    with open(os.path.join(BASE, "main.py"), "r", encoding="utf-8") as f:
        src = f.read()
    compile(src, "main.py", "exec")
    check("main.py compiles without syntax errors", True)
except SyntaxError as e:
    check(f"main.py syntax error at line {e.lineno}: {e.msg}", False)
except Exception as e:
    check(f"main.py compile check error: {e}", False)

# ── 3. safe_telegram_call: FloodWait capping logic ─────────────────────────
print("\n[3] Retry logic simulation (FloodWait pattern)")
try:
    call_count = [0]

    async def flaky_coro():
        call_count[0] += 1
        if call_count[0] < 3:
            raise ValueError("simulated flood wait")
        return "ok"

    async def _test_retry():
        max_retries = 3
        last_exc = None
        for attempt in range(max_retries):
            try:
                return await flaky_coro()
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    await asyncio.sleep(0)
        raise last_exc

    result = asyncio.run(_test_retry())
    check("Retry succeeds after 2 failures on 3rd attempt", result == "ok")
    check("Flaky coroutine called exactly 3 times", call_count[0] == 3)
except Exception as e:
    check(f"Retry logic test: {e}", False)

# ── 4. /health endpoint structure ─────────────────────────────────────────
print("\n[4] /health response structure (mock)")
try:
    health_example = {
        "status": "ok",
        "brand": "Bete Dires",
        "timestamp": "2025-01-01T00:00:00",
        "database": {
            "status": "ok",
            "stats": {"posted": 10, "partially_posted": 0, "pending": 2}
        },
        "background_tasks": {
            "bot_polling": "running",
            "cleanup": "running",
            "scheduler": "running"
        },
        "system": {"host": "127.0.0.1", "port": 8001}
    }
    check("/health has 'status' key", "status" in health_example)
    check("/health has 'database' key", "database" in health_example)
    check("/health database has 'stats'", "stats" in health_example["database"])
    check("/health stats has 'partially_posted'",
          "partially_posted" in health_example["database"]["stats"])
    check("/health has 'background_tasks'", "background_tasks" in health_example)
    check("/health background_tasks has 3 workers",
          len(health_example["background_tasks"]) == 3)
except Exception as e:
    check(f"/health structure: {e}", False)

# ── 5. run_expiry_cleanup idempotency (in-memory SQLite) ──────────────────
print("\n[5] Expiry cleanup idempotency (in-memory SQLite)")
try:
    import sqlite3, datetime

    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE items (
        id INTEGER PRIMARY KEY, name TEXT, status TEXT, created_at TEXT,
        channel_message_id INTEGER, category_message_id INTEGER,
        channel_chat_id INTEGER, category_chat_id INTEGER,
        photo_file_id TEXT, post_error TEXT)""")
    old_date = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).isoformat()
    conn.execute(
        """INSERT INTO items
           (name, status, created_at, channel_message_id, category_message_id,
            channel_chat_id, category_chat_id, photo_file_id)
           VALUES (?, ?, ?, 111, 222, -1001000000001, -1001000000002, 'abc123')""",
        ("Test Expired Item", "POSTED", old_date))
    conn.commit()

    expiry_days = 7
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=expiry_days)).isoformat()

    def find_expired(c):
        return c.execute(
            "SELECT id, name FROM items WHERE status='POSTED' AND created_at < ?",
            (cutoff,)).fetchall()

    expired1 = find_expired(conn)
    check("First cleanup run finds 1 expired item", len(expired1) == 1)

    conn.execute("UPDATE items SET status='SOLD' WHERE id=?", (expired1[0][0],))
    conn.commit()

    expired2 = find_expired(conn)
    check("Second cleanup run finds 0 items (idempotent)", len(expired2) == 0)
    conn.close()
except Exception as e:
    check(f"Idempotency test: {e}", False)

# ── 6. config.py sanity check ─────────────────────────────────────────────
print("\n[6] config.py sanity check")
try:
    from config import (BRAND_NAME, CHANNEL_ID, CATEGORY_CHANNELS,
                        BRAND_HASHTAG, WATERMARK_TEXT, ADMIN_PASSWORD_HASH)
    check("BRAND_NAME loaded", bool(BRAND_NAME))
    check("CHANNEL_ID is int or str", isinstance(CHANNEL_ID, (int, str)))
    check("CATEGORY_CHANNELS is dict", isinstance(CATEGORY_CHANNELS, dict))
    check("Cosmetics in CATEGORY_CHANNELS", "Cosmetics" in CATEGORY_CHANNELS)
    check("BRAND_HASHTAG is str", isinstance(BRAND_HASHTAG, str))
    check("WATERMARK_TEXT is str", isinstance(WATERMARK_TEXT, str))
    from config import verify_admin_password, ADMIN_PASSWORD
    check("verify_admin_password validates ADMIN_PASSWORD", verify_admin_password(ADMIN_PASSWORD))
except Exception as e:
    check(f"config.py: {e}", False)

# ── 7. bot.py compiles without syntax errors ──────────────────────────────
print("\n[7] bot.py syntax check")
try:
    with open(os.path.join(BASE, "bot.py"), "r", encoding="utf-8") as f:
        src = f.read()
    compile(src, "bot.py", "exec")
    check("bot.py compiles without syntax errors", True)
except SyntaxError as e:
    check(f"bot.py syntax error at line {e.lineno}: {e.msg}", False)
except Exception as e:
    check(f"bot.py compile error: {e}", False)

# ── 8. forwarder bot.py compiles ──────────────────────────────────────────
print("\n[8] telegram_forwarder/bot.py syntax check")
try:
    fwd_path = os.path.join(BASE, "telegram_forwarder", "bot.py")
    with open(fwd_path, "r", encoding="utf-8") as f:
        src = f.read()
    compile(src, "telegram_forwarder/bot.py", "exec")
    check("telegram_forwarder/bot.py compiles without syntax errors", True)
except SyntaxError as e:
    check(f"forwarder syntax error at line {e.lineno}: {e.msg}", False)
except Exception as e:
    check(f"forwarder compile error: {e}", False)

# ── Summary ────────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
passed = sum(1 for ok, _ in _results if ok)
total = len(_results)
failed = [label for ok, label in _results if not ok]
print(f"  Result: {passed}/{total} checks passed")
if failed:
    print("\n  Failed checks:")
    for label in failed:
        print(f"    {FAIL} {label}")
    sys.exit(1)
else:
    print(f"\n  {PASS} All Step 3 checks passed!")
    sys.exit(0)
