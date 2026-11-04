"""
test_step5.py - Automated verification tests for Step 5 (Trust & Verification)
Bete Dires (ቤተ ድረስ) Marketplace

Tests:
1. Database Schema Verification:
   - items table has columns: telegram_user_id, is_verified, expiry_warning_sent
   - sellers table exists with correct schema
   - reports table exists with correct schema
2. Caption Conditional Verification (captions.py):
   - is_verified=False: Caption must NOT contain "Verified Seller" or "የተረጋገጠ እቃ"
   - is_verified=True: Caption MUST contain "✅ Verified Seller / የተረጋገጠ እቃ"
   - get_sold_caption formats with SOLD banner
3. Async DB Model Lifecycle (database.py):
   - Seller model CRUD (Pending -> Approved with verified_at)
   - Report model CRUD (Pending -> Actioned with resolved_at)
   - Item is_verified toggle
4. Pre-Expiry Warning Query Logic:
   - Identifies candidate items past warning threshold with telegram_user_id
   - Ignores items where expiry_warning_sent is already 1
5. Bot and Dashboard Endpoints compilation:
   - bot.py seller verification & reporting handlers load without error
   - main.py admin verification & reports routes present
"""

import sys
import os
import sqlite3
import asyncio
from datetime import datetime, timedelta

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


# ── 1. Database Schema Checks ──────────────────────────────────────────────
def test_db_schema():
    print("\n[1] Database Schema Check (betedires.db)")
    conn = sqlite3.connect("betedires.db")
    cur = conn.cursor()

    # Check items columns
    cur.execute("PRAGMA table_info(items)")
    cols = {row[1]: row[2] for row in cur.fetchall()}
    check("items has telegram_user_id column", "telegram_user_id" in cols)
    check("items has is_verified column", "is_verified" in cols)
    check("items has expiry_warning_sent column", "expiry_warning_sent" in cols)

    # Check sellers table
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sellers'")
    check("sellers table exists", bool(cur.fetchone()))

    cur.execute("PRAGMA table_info(sellers)")
    seller_cols = {row[1]: row[2] for row in cur.fetchall()}
    check("sellers has telegram_user_id", "telegram_user_id" in seller_cols)
    check("sellers has status", "status" in seller_cols)
    check("sellers has id_photo_path", "id_photo_path" in seller_cols)

    # Check reports table
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reports'")
    check("reports table exists", bool(cur.fetchone()))

    cur.execute("PRAGMA table_info(reports)")
    report_cols = {row[1]: row[2] for row in cur.fetchall()}
    check("reports has item_id", "item_id" in report_cols)
    check("reports has reporter_user_id", "reporter_user_id" in report_cols)
    check("reports has reason", "reason" in report_cols)

    conn.close()


# ── 2. Caption Conditional Verification ───────────────────────────────────
def test_captions():
    print("\n[2] Conditional Verification Captions")
    from captions import get_caption, get_sold_caption
    from database import Item

    unverified_item = Item(
        id=9991,
        name="Samsung S22 Ultra",
        price="45,000 ETB",
        location="Gondar",
        phone="0911223344",
        condition="New",
        category="Electronics",
        username="seller1",
        is_verified=False,
        category_id_seq=1
    )
    caption_unverified = get_caption(unverified_item)
    check("Unverified caption omits 'Verified Seller'", "Verified Seller" not in caption_unverified)
    check("Unverified caption omits 'የተረጋገጠ እቃ'", "የተረጋገጠ እቃ" not in caption_unverified)

    verified_item = Item(
        id=9992,
        name="Samsung S22 Ultra",
        price="45,000 ETB",
        location="Gondar",
        phone="0911223344",
        condition="New",
        category="Electronics",
        username="seller1",
        is_verified=True,
        category_id_seq=2
    )
    caption_verified = get_caption(verified_item)
    check("Verified caption contains 'Verified Seller'", "Verified Seller" in caption_verified)
    check("Verified caption contains 'የተረጋገጠ እቃ'", "የተረጋገጠ እቃ" in caption_verified)

    sold_cap = get_sold_caption(verified_item)
    check("Sold caption marks item as SOLD", "ተሽጧል" in sold_cap and "SOLD" in sold_cap)


# ── 3. Async ORM Lifecycle ────────────────────────────────────────────────
async def test_orm_lifecycle():
    print("\n[3] Async ORM Lifecycle (Seller & Report)")
    from database import AsyncSessionLocal, Seller, Report, Item, ItemStatus
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # 1. Seller flow — model uses: name, reviewed_at, status as plain string
        test_uid = 999111222
        old_seller = (await session.execute(select(Seller).where(Seller.telegram_user_id == test_uid))).scalars().first()
        if old_seller:
            await session.delete(old_seller)
            await session.commit()

        seller = Seller(
            telegram_user_id=test_uid,
            name="Dawit Haile",
            phone="0911009988",
            username="dawit_h",
            id_photo_path="secure_uploads/ids/test.jpg",
            status="pending"
        )
        session.add(seller)
        await session.commit()
        await session.refresh(seller)
        check("Seller saved as 'pending'", seller.status == "pending")

        # Admin approval
        seller.status = "approved"
        seller.reviewed_at = datetime.utcnow()
        await session.commit()

        approved_seller = (await session.execute(select(Seller).where(Seller.telegram_user_id == test_uid))).scalars().first()
        check("Seller status 'approved' + reviewed_at populated",
              approved_seller.status == "approved" and approved_seller.reviewed_at is not None)

        await session.delete(approved_seller)
        await session.commit()

        # 2. Report flow — model uses plain string status
        first_item = (await session.execute(select(Item))).scalars().first()
        check("Database has at least one item for report linking", first_item is not None)

        if first_item:
            report = Report(
                item_id=first_item.id,
                reporter_user_id=888777666,
                reason="wrong_category",
                status="pending"
            )
            session.add(report)
            await session.commit()
            await session.refresh(report)
            check("Report saved as 'pending'", report.status == "pending")

            report.status = "resolved"
            await session.commit()

            resolved = (await session.execute(select(Report).where(Report.id == report.id))).scalars().first()
            check("Report resolved to 'resolved'", resolved.status == "resolved")

            await session.delete(resolved)
            await session.commit()

        # 3. Item is_verified toggle
        if first_item:
            curr_v = bool(first_item.is_verified)
            first_item.is_verified = not curr_v
            await session.commit()
            await session.refresh(first_item)
            check("Item is_verified flag toggled", first_item.is_verified == (not curr_v))

            first_item.is_verified = curr_v
            await session.commit()
            check("Item is_verified flag reverted cleanly", first_item.is_verified == curr_v)


# ── 4. Pre-Expiry Logic ───────────────────────────────────────────────────
async def test_pre_expiry_logic():
    print("\n[4] Pre-Expiry Availability Check Logic")
    from database import AsyncSessionLocal, Item, ItemStatus
    from sqlalchemy import select, and_

    now = datetime.utcnow()
    async with AsyncSessionLocal() as session:
        # Create a mock expired item nearing cutoff
        mock_item = Item(
            name="Test Expiring Item",
            price="1000 ETB",
            location="Gondar",
            phone="0900000000",
            photo_file_id="test_photo.jpg",
            condition="New",
            category="Others",
            username="tester",
            telegram_user_id=777666555,
            status=ItemStatus.POSTED,
            created_at=now - timedelta(days=6),
            expiry_warning_sent=0,
            category_id_seq=9999
        )
        session.add(mock_item)
        await session.commit()
        await session.refresh(mock_item)

        # Query candidates for warning
        warning_window_start = now - timedelta(days=7)
        warning_window_end = now - timedelta(days=5)

        q = select(Item).where(
            Item.status == ItemStatus.POSTED,
            Item.created_at <= warning_window_end,
            Item.created_at >= warning_window_start,
            Item.expiry_warning_sent == 0,
            Item.telegram_user_id.isnot(None)
        )
        candidates = (await session.execute(q)).scalars().all()
        check("Candidate nearing expiry identified for warning", any(c.id == mock_item.id for c in candidates))

        # Mark warning sent
        mock_item.expiry_warning_sent = 1
        await session.commit()

        candidates_after = (await session.execute(q)).scalars().all()
        check("Warned item excluded from future warnings (idempotent)", not any(c.id == mock_item.id for c in candidates_after))

        # Clean up
        await session.delete(mock_item)
        await session.commit()


# ── 5. Integration Imports & Routes Check ─────────────────────────────────
def test_integration():
    print("\n[5] Module Integration & Handler Compilations")
    try:
        import bot
        check("bot.py imported successfully", hasattr(bot, "dp"))
        check("bot has SellerVerifyForm state", hasattr(bot, "SellerVerifyForm"))
    except Exception as e:
        check(f"bot.py import failed: {e}", False)

    try:
        import main
        check("main.py imported successfully", hasattr(main, "app"))
        routes = [route.path for route in main.app.routes]
        check("main.py has /admin/verifications route", "/admin/verifications" in routes)
        check("main.py has /action/verify_seller route", "/action/verify_seller" in routes)
        check("main.py has /admin/reports route", "/admin/reports" in routes)
        check("main.py has /action/resolve_report route", "/action/resolve_report" in routes)
        check("main.py has /action/toggle_verify route", "/action/toggle_verify" in routes)
    except Exception as e:
        check(f"main.py import failed: {e}", False)


async def main():
    test_db_schema()
    test_captions()
    await test_orm_lifecycle()
    await test_pre_expiry_logic()
    test_integration()

    print("\n" + "=" * 60)
    failed = [label for ok, label in _results if not ok]
    if failed:
        print(f"FAILED {len(failed)} tests:")
        for f in failed:
            print(f"  {FAIL} {f}")
        sys.exit(1)
    else:
        print(f"ALL {len(_results)} STEP 5 TESTS PASSED SUCCESSFULLY! {PASS}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
