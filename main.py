import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, BackgroundTasks, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.future import select
from sqlalchemy import delete, func, text
from datetime import datetime, timedelta, timezone
import os
import uuid
import re
import logging
import logging.handlers

from database import init_db, AsyncSessionLocal, Item, ItemStatus, Settings, Seller, Report, SearchAlert, UserPreference, Order
from bot import bot, dp
from utils import apply_watermark, scrape_telegram_photos, is_valid_image
from search_engine import check_search_alerts
from captions import get_item_serial, get_caption, get_sold_caption
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse, FileResponse
from aiogram.types import BufferedInputFile, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import (
    TelegramRetryAfter,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramAPIError
)

from config import (
    BRAND_NAME,
    BRAND_HASHTAG,
    WATERMARK_TEXT,
    CHANNEL_ID,
    ADMIN_USERNAME_TEMPLATE,
    CATEGORY_CHANNELS,
    ITEM_SHORTHANDS,
    CATEGORY_TAGS,
    SERVER_HOST,
    SERVER_PORT,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE_SECONDS,
    verify_admin_password,
    create_session_token,
    verify_session_token,
    get_csrf_token,
    verify_csrf_token
)

# Structured Logging Configuration
os.makedirs("logs", exist_ok=True)
logger = logging.getLogger("BeteDires_Suite")
logger.setLevel(logging.INFO)

if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s'))
    logger.addHandler(ch)

    fh = logging.handlers.RotatingFileHandler("logs/app.log", maxBytes=1024*1024*5, backupCount=5, encoding="utf-8")
    fh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s'))
    logger.addHandler(fh)
logger.propagate = False

# Global registry for background task monitoring via /health
background_tasks: dict[str, asyncio.Task | None] = {
    "bot_polling": None,
    "cleanup_worker": None,
    "scheduler_worker": None
}

templates = Jinja2Templates(directory="templates")

async def safe_telegram_call(coro_fn, max_retries: int = 3, max_wait_sec: int = 35):
    """
    Executes a Telegram API call with exponential backoff and FloodWait (TelegramRetryAfter) handling.
    """
    for attempt in range(max_retries):
        try:
            return await coro_fn()
        except TelegramRetryAfter as e:
            wait_time = min(e.retry_after, max_wait_sec)
            logger.warning(f"Telegram FloodWait encountered: waiting {wait_time}s (attempt {attempt+1}/{max_retries})")
            if e.retry_after > max_wait_sec and attempt == max_retries - 1:
                raise
            await asyncio.sleep(wait_time)
        except TelegramNetworkError as e:
            wait_time = 2 ** attempt
            logger.warning(f"Telegram network glitch ({e}): retrying in {wait_time}s (attempt {attempt+1}/{max_retries})")
            await asyncio.sleep(wait_time)
        except Exception:
            raise

async def run_expiry_cleanup() -> dict:
    """
    Idempotently cleans up expired posts from Telegram and the database.
    Processes each expired item in its own isolated transaction so that failure on one
    item does not roll back deletions of others.
    """
    stats = {"inspected": 0, "deleted": 0, "errors": 0}
    try:
        async with AsyncSessionLocal() as session:
            settings_res = await session.execute(select(Settings).limit(1))
            settings = settings_res.scalar_one_or_none()
            expiry_days = settings.expiry_days if settings else 7
            
            expiry_date = datetime.now() - timedelta(days=expiry_days)
            
            result = await session.execute(
                select(Item).where(
                    Item.status != ItemStatus.PENDING,
                    Item.created_at < expiry_date
                )
            )
            expired_items = result.scalars().all()
            stats["inspected"] = len(expired_items)

        if not expired_items:
            logger.info("Expiry Worker: No expired posts found.")
            return stats

        logger.info(f"Expiry Worker: Found {len(expired_items)} expired items (threshold: >{expiry_days} days). Starting idempotent cleanup...")

        for item_data in expired_items:
            item_id = item_data.id
            item_name = item_data.name
            target_main = item_data.channel_chat_id or CHANNEL_ID
            target_cat = item_data.category_chat_id or CATEGORY_CHANNELS.get(item_data.category)
            main_msg_id = item_data.channel_message_id
            cat_msg_id = item_data.category_message_id
            created_str = item_data.created_at.strftime("%Y-%m-%d %H:%M:%S") if item_data.created_at else "unknown"

            # 1. Attempt Telegram main channel deletion (idempotent)
            main_del_status = "none"
            if main_msg_id:
                try:
                    await safe_telegram_call(lambda: bot.delete_message(chat_id=target_main, message_id=main_msg_id))
                    main_del_status = "deleted"
                except TelegramBadRequest as e:
                    main_del_status = f"already_deleted_or_missing ({e.message})"
                except Exception as e:
                    main_del_status = f"failed ({e})"

            # 2. Attempt Telegram category channel deletion (idempotent)
            cat_del_status = "none"
            if cat_msg_id and target_cat:
                try:
                    await safe_telegram_call(lambda: bot.delete_message(chat_id=target_cat, message_id=cat_msg_id))
                    cat_del_status = "deleted"
                except TelegramBadRequest as e:
                    cat_del_status = f"already_deleted_or_missing ({e.message})"
                except Exception as e:
                    cat_del_status = f"failed ({e})"

            # 3. Clean up in DB within an isolated transaction
            try:
                async with AsyncSessionLocal() as del_session:
                    it = await del_session.get(Item, item_id)
                    if it:
                        # Clean up any local upload files if present
                        if it.photo_file_id:
                            for photo_ref in it.photo_file_id.split(","):
                                if photo_ref.startswith("local:"):
                                    fname = photo_ref.replace("local:", "")
                                    fpath = os.path.join("uploads", fname)
                                    if os.path.exists(fpath):
                                        try:
                                            os.remove(fpath)
                                        except Exception:
                                            pass
                        await del_session.delete(it)
                        await del_session.commit()
                        stats["deleted"] += 1
                        logger.info(
                            f"Expiry Worker [Audit]: Deleted expired item ID={item_id} "
                            f"('{item_name}', created: {created_str}). "
                            f"Main [{target_main} msg {main_msg_id}]: {main_del_status}; "
                            f"Category [{target_cat} msg {cat_msg_id}]: {cat_del_status}"
                        )
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Expiry Worker: Failed to delete item ID={item_id} from DB: {e}")

    except Exception as e:
        logger.error(f"Expiry Worker unhandled error: {e}")

    logger.info(f"Expiry Worker: Cleanup completed. Inspected: {stats['inspected']}, Deleted: {stats['deleted']}, Errors: {stats['errors']}")
    return stats

async def run_pre_expiry_check() -> int:
    """
    Finds items approaching expiry (Day 6 of 7) and messages sellers to ask:
    'Is this item still available?' with Still Available / Mark as Sold buttons.
    """
    cutoff_warning = datetime.utcnow() - timedelta(days=6)
    warned_count = 0
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Item).where(
                    Item.status == ItemStatus.POSTED,
                    Item.created_at < cutoff_warning,
                    Item.expiry_warning_sent == 0,
                    Item.telegram_user_id.isnot(None)
                )
            )
            items_to_warn = result.scalars().all()
            for item in items_to_warn:
                try:
                    serial = get_item_serial(item)
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="✅ አሁንም አለ (Still Available)", callback_data=f"avail:keep:{item.id}"),
                            InlineKeyboardButton(text="❌ ተሽጧል (Sold)", callback_data=f"avail:sold:{item.id}")
                        ]
                    ])
                    msg_text = (
                        f"⏰ <b>የእቃ መረጃ ማረጋገጫ / Availability Check</b>\n\n"
                        f"የለጠፉት እቃ: <b>{html.escape(item.name)}</b> ({serial})\n"
                        f"ዋጋ: <code>{html.escape(item.price)}</code> ብር\n\n"
                        "ይህ እቃ አሁንም ይገኛል ወይስ ተሽጧል?\n"
                        "(Is this item still available? If no response, it will expire in 24 hours.)"
                    )
                    await bot.send_message(
                        chat_id=item.telegram_user_id,
                        text=msg_text,
                        parse_mode="HTML",
                        reply_markup=kb
                    )
                    item.expiry_warning_sent = 1
                    warned_count += 1
                except Exception as e:
                    logger.warning(f"Could not send pre-expiry warning to seller {item.telegram_user_id} for item {item.id}: {e}")
            await session.commit()
    except Exception as e:
        logger.error(f"Error during pre-expiry warning run: {e}")
    return warned_count

async def cleanup_expired_posts_loop():
    logger.info("Expiry Worker: Background task started. Will sweep daily.")
    while True:
        try:
            await run_pre_expiry_check()
            await run_expiry_cleanup()
        except Exception as e:
            logger.error(f"Expiry Worker loop error: {e}")
        await asyncio.sleep(86400) # Check once a day

async def run_sqlite_backup() -> str | None:
    """
    Creates a timestamped snapshot of betedires.db in backups/ directory
    using sqlite3 online backup API (safe while database is actively running).
    Rotates old backups keeping the newest 14 snapshots.
    """
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"betedires_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    source_db = "betedires.db"
    if not os.path.exists(source_db):
        logger.error(f"Backup failed: source database '{source_db}' does not exist.")
        return None
        
    try:
        import sqlite3
        src_conn = sqlite3.connect(source_db)
        dst_conn = sqlite3.connect(backup_path)
        with dst_conn:
            src_conn.backup(dst_conn)
        src_conn.close()
        dst_conn.close()
        
        file_size_kb = round(os.path.getsize(backup_path) / 1024, 1)
        logger.info(f"SQLite Backup: Created snapshot '{backup_filename}' ({file_size_kb} KB) successfully.")
        
        # Retention rotation: keep newest 14 backups
        all_backups = sorted([
            os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
            if f.startswith("betedires_backup_") and f.endswith(".db")
        ], key=os.path.getmtime, reverse=True)
        
        if len(all_backups) > 14:
            for old_file in all_backups[14:]:
                try:
                    os.remove(old_file)
                    logger.info(f"SQLite Backup: Rotated old backup '{os.path.basename(old_file)}'.")
                except Exception as e:
                    logger.warning(f"SQLite Backup: Could not delete old backup '{old_file}': {e}")
                    
        return backup_filename
    except Exception as e:
        logger.error(f"SQLite Backup error: {e}", exc_info=True)
        return None

async def daily_backup_loop():
    logger.info("Backup Worker: Background daily backup loop started.")
    await asyncio.sleep(60) # Wait 60s after startup
    while True:
        try:
            await run_sqlite_backup()
        except Exception as e:
            logger.error(f"Backup Worker loop error: {e}")
        await asyncio.sleep(86400) # Run every 24 hours

async def publish_item_to_telegram(item: Item, target_channels: list[str] | None = None) -> tuple[int | None, int | None, dict[str, str]]:
    """
    Publishes an item to Telegram channels with automatic FloodWait / rate-limit backoff.
    Returns (main_msg_id, cat_msg_id, errors_dict).
    """
    errors: dict[str, str] = {}
    main_msg_id = item.channel_message_id
    cat_msg_id = item.category_message_id

    # Telegram only allows max 10 photos in a media group
    photo_ids = [p.strip() for p in (item.photo_file_id or "").split(",") if p.strip()][:10]
    if not photo_ids:
        err_msg = "No photos associated with this item."
        logger.error(f"Publish failed for item {item.id}: {err_msg}")
        return main_msg_id, cat_msg_id, {"media": err_msg}

    # Pre-process watermarked bytes
    watermarked_files = []
    for idx, f_id in enumerate(photo_ids):
        try:
            if f_id.startswith("local:"):
                filename = f_id.replace("local:", "")
                filepath = os.path.join("uploads", filename)
                with open(filepath, "rb") as f:
                    raw_bytes = f.read()
            else:
                file = await safe_telegram_call(lambda: bot.get_file(f_id))
                pb = await safe_telegram_call(lambda: bot.download_file(file.file_path))
                raw_bytes = pb.read()
                
            watermarked_bytes = apply_watermark(raw_bytes)
            watermarked_files.append((f"wm_{idx}.jpg", watermarked_bytes))
        except Exception as e:
            logger.warning(f"Failed to process photo index {idx} ({f_id}) for item {item.id}: {e}")

    if not watermarked_files:
        err_msg = "Failed to load any images for this item."
        logger.error(f"Publish failed for item {item.id}: {err_msg}")
        return main_msg_id, cat_msg_id, {"media": err_msg}

    # Build engagement markup
    admin_user = ADMIN_USERNAME_TEMPLATE.replace('@', '')
    main_user = CHANNEL_ID.replace('@', '')
    admin_btn = InlineKeyboardButton(text="📩 እቃ ለመሸጥ", url=f"https://t.me/{admin_user}")
    gallery_btn = InlineKeyboardButton(text="🔗 እቃዎችን ለመመልከት", url=f"https://t.me/{main_user}")
    markup = InlineKeyboardMarkup(inline_keyboard=[[admin_btn, gallery_btn]])
            
    main_channel = item.channel_chat_id or CHANNEL_ID
    cat_channel = item.category_chat_id or CATEGORY_CHANNELS.get(item.category)
    item.channel_chat_id = main_channel
    item.category_chat_id = cat_channel

    if target_channels is not None:
        channels_to_post = [ch for ch in target_channels if ch]
    else:
        channels_to_post = [main_channel]
        if cat_channel and cat_channel != main_channel:
            channels_to_post.append(cat_channel)

    for current_channel in channels_to_post:
        media_group = []
        for idx, (fname, w_bytes) in enumerate(watermarked_files):
            if idx == 0:
                media_group.append(InputMediaPhoto(media=BufferedInputFile(w_bytes, filename=fname), caption=get_caption(item), parse_mode="HTML"))
            else:
                media_group.append(InputMediaPhoto(media=BufferedInputFile(w_bytes, filename=fname)))

        channel_succeeded = False
        msg_id = None

        # Attempt 1: Rich HTML Mode
        try:
            if len(media_group) == 1:
                msg = await safe_telegram_call(lambda: bot.send_photo(
                    chat_id=current_channel,
                    photo=media_group[0].media,
                    caption=media_group[0].caption,
                    parse_mode="HTML",
                    reply_markup=markup
                ))
                msg_id = msg.message_id
            else:
                msgs = await safe_telegram_call(lambda: bot.send_media_group(chat_id=current_channel, media=media_group))
                try:
                    await safe_telegram_call(lambda: bot.send_message(
                        chat_id=current_channel,
                        text="👆 <i>Browse more items or contact admin below:</i>",
                        parse_mode="HTML",
                        reply_markup=markup,
                        reply_to_message_id=msgs[0].message_id
                    ))
                except Exception:
                    pass
                msg_id = msgs[0].message_id
            channel_succeeded = True
        except Exception as e_html:
            logger.warning(f"HTML mode publish to {current_channel} failed for item {item.id} ({e_html}), attempting plain fallback...")
            # Attempt 2: Plain Text Fallback
            try:
                if len(media_group) == 1:
                    media_group[0].media = BufferedInputFile(watermarked_files[0][1], filename=watermarked_files[0][0])
                    msg = await safe_telegram_call(lambda: bot.send_photo(
                        chat_id=current_channel,
                        photo=media_group[0].media,
                        caption=get_caption(item),
                        reply_markup=markup
                    ))
                    msg_id = msg.message_id
                else:
                    for i in range(len(media_group)):
                        media_group[i].media = BufferedInputFile(watermarked_files[i][1], filename=watermarked_files[i][0])
                    media_group[0].caption = get_caption(item)
                    media_group[0].parse_mode = None
                    msgs = await safe_telegram_call(lambda: bot.send_media_group(chat_id=current_channel, media=media_group))
                    msg_id = msgs[0].message_id
                channel_succeeded = True
            except Exception as e_plain:
                error_desc = str(e_plain) or str(e_html)
                logger.error(f"Failed to post item {item.id} to channel {current_channel}: {error_desc}")
                errors[current_channel] = error_desc

        if channel_succeeded and msg_id:
            if current_channel == main_channel:
                main_msg_id = msg_id
            else:
                cat_msg_id = msg_id

    return main_msg_id, cat_msg_id, errors

def get_auth_token(request: Request) -> str | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if verify_session_token(token):
        return token
    return None

def verify_form_csrf(request: Request, csrf_token: str):
    session_token = get_auth_token(request)
    if not session_token or not verify_csrf_token(csrf_token, session_token):
        raise HTTPException(status_code=403, detail="Forbidden: Invalid or expired session / CSRF token")

async def process_scheduled_posts_loop():
    logger.info("Scheduler: Background polling loop started.")
    while True:
        try:
            async with AsyncSessionLocal() as session:
                now = datetime.now()
                # Find items that are ready to post
                result = await session.execute(
                    select(Item).where(
                        Item.status == ItemStatus.SCHEDULED,
                        Item.scheduled_time <= now
                    )
                )
                items_to_post = result.scalars().all()
                if items_to_post:
                    logger.info(f"Scheduler: Found {len(items_to_post)} items to publish.")
                    
                for item in items_to_post:
                    try:
                        logger.info(f"Scheduler: Publishing item '{item.name}' (ID: {item.id})...")
                        main_id, cat_id, errors = await publish_item_to_telegram(item)
                        if main_id:
                            item.channel_message_id = main_id
                        if cat_id:
                            item.category_message_id = cat_id

                        expected_channels = 2 if (item.category_chat_id and item.category_chat_id != item.channel_chat_id) else 1
                        posted_channels = (1 if item.channel_message_id else 0) + (1 if item.category_message_id else 0)

                        if posted_channels >= expected_channels:
                            item.status = ItemStatus.POSTED
                            item.post_error = None
                            logger.info(f"Scheduler: Successfully published: '{item.name}' (ID: {item.id})")
                            asyncio.create_task(check_search_alerts(item, bot))
                        elif posted_channels > 0:
                            item.status = ItemStatus.PARTIALLY_POSTED
                            err_desc = "; ".join([f"{ch}: {err}" for ch, err in errors.items()])
                            item.post_error = err_desc or "Partial scheduler publish."
                            logger.warning(f"Scheduler: Item '{item.name}' partially published: {item.post_error}")
                        else:
                            err_desc = "; ".join([f"{ch}: {err}" for ch, err in errors.items()])
                            item.post_error = f"Scheduler publish failed: {err_desc}"
                            logger.error(f"Scheduler: Failed to publish '{item.name}': {item.post_error}")

                        await session.commit()
                    except Exception as e:
                        logger.error(f"Scheduler: Error publishing item {item.id}: {e}")
        except Exception as e:
            logger.error(f"Scheduler: Main loop error: {e}")
            
        await asyncio.sleep(20)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB
    await init_db()
    
    def handle_bot_task_result(task):
        try:
            task.result()
        except Exception as e:
            logger.error(f"Bot polling crashed with error: {e}")
            
    # Try deleting any conflicting webhook first to fix Telegram sync issues
    async def run_bot_polling():
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
        
    bot_task = asyncio.create_task(run_bot_polling())
    bot_task.add_done_callback(handle_bot_task_result)
    background_tasks["bot_polling"] = bot_task
    
    # Start background cleanup, backup, and scheduler loops
    cleanup_task = asyncio.create_task(cleanup_expired_posts_loop())
    background_tasks["cleanup_worker"] = cleanup_task
    
    backup_task = asyncio.create_task(daily_backup_loop())
    background_tasks["backup_worker"] = backup_task
    
    scheduler_task = asyncio.create_task(process_scheduled_posts_loop())
    background_tasks["scheduler_worker"] = scheduler_task
    
    yield
    
    # Shutdown
    bot_task.cancel()
    cleanup_task.cancel()
    backup_task.cancel()
    scheduler_task.cancel()
    await bot.session.close()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

def extract_raw_price(price_str: str) -> float:
    if not price_str:
        return 0.0
    clean = re.sub(r'[^\d.]', '', str(price_str).replace(',', ''))
    try:
        return float(clean)
    except Exception:
        return 0.0

@app.get("/login")
async def login_page(request: Request):
    if get_auth_token(request):
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"request": request, "brand_name": BRAND_NAME, "error": None}
    )

@app.post("/login")
async def process_login(request: Request, password: str = Form(...)):
    if verify_admin_password(password):
        token = create_session_token()
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            max_age=SESSION_MAX_AGE_SECONDS,
            httponly=True,
            samesite="lax"
        )
        return response
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"request": request, "brand_name": BRAND_NAME, "error": "Invalid admin password."},
        status_code=401
    )

@app.get("/logout")
async def process_logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response

# ========================================================
# Customer-Facing Marketplace (Bete Dires Storefront)
# ========================================================

@app.get("/")
async def store_home(request: Request, category: str = "All"):
    """
    Public customer-facing marketplace (Bete Dires Storefront).
    Alibaba-style search, filtering, and Telegram order routing.
    """
    is_admin = bool(get_auth_token(request))
    admin_handle = ADMIN_USERNAME_TEMPLATE.replace('@', '')

    async with AsyncSessionLocal() as session:
        query = select(Item).where(
            Item.status.in_([ItemStatus.POSTED, ItemStatus.PARTIALLY_POSTED])
        )
        if category != "All":
            query = query.where(Item.category == category)
            
        result = await session.execute(query.order_by(Item.id.desc()))
        items_db = result.scalars().all()

        cat_counts_res = await session.execute(
            select(Item.category, func.count(Item.id)).where(
                Item.status.in_([ItemStatus.POSTED, ItemStatus.PARTIALLY_POSTED])
            ).group_by(Item.category)
        )
        category_counts = {cat or "Others": count for cat, count in cat_counts_res.all()}

        hydrated_items = []
        for it in items_db:
            raw_p = extract_raw_price(it.price)
            hydrated_items.append({
                "item": it,
                "serial": get_item_serial(it),
                "raw_price": raw_p
            })

    return templates.TemplateResponse(
        request=request,
        name="store.html",
        context={
            "request": request,
            "brand_name": BRAND_NAME,
            "channel_id": CHANNEL_ID,
            "admin_username": admin_handle,
            "items": hydrated_items,
            "category_counts": category_counts,
            "is_admin": is_admin,
            "meta_title": f"{BRAND_NAME} - Doorstep Delivery Marketplace",
            "meta_desc": "በአስተማማኝ መንገድ እቃዎችን ይፈልጉ፣ ይዘዙ እና ቤትዎ ድረስ አስመጥተው አይተው ከፍለው ይቀበሉ። ቤቴ ድረስ",
            "meta_image": "/static/logo.png"
        }
    )

@app.get("/item/{item_id}")
async def item_detail_view(request: Request, item_id: int):
    """
    Direct item view page with Telegram Open Graph preview cards.
    """
    is_admin = bool(get_auth_token(request))
    admin_handle = ADMIN_USERNAME_TEMPLATE.replace('@', '')

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Item).where(Item.id == item_id))
        target_item = res.scalar_one_or_none()

        query = select(Item).where(
            Item.status.in_([ItemStatus.POSTED, ItemStatus.PARTIALLY_POSTED])
        )
        result = await session.execute(query.order_by(Item.id.desc()))
        items_db = result.scalars().all()

        cat_counts_res = await session.execute(
            select(Item.category, func.count(Item.id)).where(
                Item.status.in_([ItemStatus.POSTED, ItemStatus.PARTIALLY_POSTED])
            ).group_by(Item.category)
        )
        category_counts = {cat or "Others": count for cat, count in cat_counts_res.all()}

        hydrated_items = []
        for it in items_db:
            raw_p = extract_raw_price(it.price)
            hydrated_items.append({
                "item": it,
                "serial": get_item_serial(it),
                "raw_price": raw_p
            })

    meta_title = f"{target_item.name} ({target_item.price} ብር) - {BRAND_NAME}" if target_item else BRAND_NAME
    meta_desc = f"{target_item.name} | ሁኔታ: {target_item.condition} | ቦታ: {target_item.location} | ዋጋ: {target_item.price} ብር - ቤቴ ድረስ" if target_item else ""
    meta_image = f"/photo/{target_item.photo_file_id}" if target_item else "/static/logo.png"

    return templates.TemplateResponse(
        request=request,
        name="store.html",
        context={
            "request": request,
            "brand_name": BRAND_NAME,
            "channel_id": CHANNEL_ID,
            "admin_username": admin_handle,
            "items": hydrated_items,
            "category_counts": category_counts,
            "is_admin": is_admin,
            "meta_title": meta_title,
            "meta_desc": meta_desc,
            "meta_image": meta_image,
            "auto_open_item_id": item_id
        }
    )

@app.get("/api/products")
async def api_search_products(category: str = "All"):
    """
    Instant JSON API for search and client filtering.
    """
    async with AsyncSessionLocal() as session:
        query = select(Item).where(
            Item.status.in_([ItemStatus.POSTED, ItemStatus.PARTIALLY_POSTED])
        )
        if category != "All":
            query = query.where(Item.category == category)

        result = await session.execute(query.order_by(Item.id.desc()))
        items_db = result.scalars().all()

        products = []
        for it in items_db:
            raw_p = extract_raw_price(it.price)
            products.append({
                "id": it.id,
                "name": it.name,
                "serial": get_item_serial(it),
                "price": it.price,
                "raw_price": raw_p,
                "category": it.category or "Others",
                "condition": it.condition or "Inspected",
                "location": it.location or "",
                "is_verified": it.is_verified,
                "photo_url": f"/photo/{it.photo_file_id}"
            })

        return JSONResponse({"success": True, "count": len(products), "products": products})

@app.post("/api/order")
async def api_create_order(request: Request):
    """
    Receives an order inquiry from the storefront and logs it into betedires.db.
    Returns success confirmation and Telegram direct admin URL.
    """
    try:
        data = await request.json()
        item_id = data.get("item_id")
        item_name = data.get("item_name") or "Item"
        item_serial = data.get("item_serial")
        item_quality = data.get("item_quality")
        quantity = int(data.get("quantity") or 1)
        total_price = data.get("total_price")
        customer_city = data.get("customer_city") or "Addis Ababa"
        customer_location = data.get("customer_location") or customer_city
        customer_phone = data.get("customer_phone")
        customer_note = data.get("customer_note")

        async with AsyncSessionLocal() as session:
            new_order = Order(
                item_id=item_id,
                item_name=item_name,
                item_serial=item_serial,
                item_quality=item_quality,
                quantity=quantity,
                total_price=total_price,
                customer_city=customer_city,
                customer_location=customer_location,
                customer_phone=customer_phone,
                customer_note=customer_note,
                telegram_target=ADMIN_USERNAME_TEMPLATE,
                status="pending"
            )
            session.add(new_order)
            await session.commit()
            await session.refresh(new_order)

            logger.info(f"New web order inquiry logged: Order #{new_order.id} for {item_name} -> {customer_location}")
            return JSONResponse({
                "success": True,
                "order_id": new_order.id,
                "admin_username": ADMIN_USERNAME_TEMPLATE
            })
    except Exception as e:
        logger.error(f"Failed to record web order inquiry: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)

# ========================================================
# Administrator Dashboard Routes
# ========================================================

@app.get("/admin")
@app.get("/admin/dashboard")
async def admin_dashboard(request: Request, category: str = "All", status: str = "All"):
    session_token = get_auth_token(request)
    if not session_token:
        return RedirectResponse(url="/login", status_code=303)
    csrf_token = get_csrf_token(session_token)

    async with AsyncSessionLocal() as session:
        query = select(Item)
        
        if category != "All":
            query = query.where(Item.category == category)
            
        if status != "All":
            query = query.where(Item.status == status)
            
        result = await session.execute(query.order_by(Item.id.desc()))
        items = result.scalars().all()
        
        # Get expiry setting
        settings_res = await session.execute(select(Settings).where(Settings.id == 1))
        settings = settings_res.scalar_one_or_none()
        expiry_days = settings.expiry_days if settings else 7
        
        # Calculate Analytics
        count_posted = (await session.execute(select(func.count(Item.id)).where(Item.status == ItemStatus.POSTED))).scalar() or 0
        count_partially_posted = (await session.execute(select(func.count(Item.id)).where(Item.status == ItemStatus.PARTIALLY_POSTED))).scalar() or 0
        count_sold = (await session.execute(select(func.count(Item.id)).where(Item.status == ItemStatus.SOLD))).scalar() or 0
        count_pending = (await session.execute(select(func.count(Item.id)).where(Item.status == ItemStatus.PENDING))).scalar() or 0
        count_scheduled = (await session.execute(select(func.count(Item.id)).where(Item.status == ItemStatus.SCHEDULED))).scalar() or 0
        
        count_pending_verifications = (await session.execute(
            select(func.count(Seller.id)).where(Seller.status == "pending")
        )).scalar() or 0
        count_pending_reports = (await session.execute(
            select(func.count(Report.id)).where(Report.status == "pending")
        )).scalar() or 0

        # Inbound web orders
        count_orders = (await session.execute(select(func.count(Order.id)))).scalar() or 0
        recent_orders_res = await session.execute(select(Order).order_by(Order.id.desc()).limit(15))
        recent_orders = recent_orders_res.scalars().all()

        total_tracked = count_posted + count_sold + count_partially_posted
        sold_rate = round((count_sold / total_tracked * 100), 1) if total_tracked > 0 else 0.0

        count_searches = (await session.execute(select(func.count(SearchAlert.id)))).scalar() or 0
        count_active_sellers = (await session.execute(
            select(func.count(func.distinct(Item.phone))).where(Item.status.in_([ItemStatus.POSTED, ItemStatus.PARTIALLY_POSTED]))
        )).scalar() or 0
        count_approved_sellers = (await session.execute(
            select(func.count(Seller.id)).where(Seller.status == "approved")
        )).scalar() or 0

        cat_group_res = (await session.execute(
            select(Item.category, func.count(Item.id)).group_by(Item.category)
        )).all()
        category_breakdown = {cat or "Others": cnt for cat, cnt in cat_group_res}
        
        # Hydrate items with serials for display
        items_with_serials = []
        for it in items:
            items_with_serials.append({
                "item": it,
                "serial": get_item_serial(it)
            })
        
    return templates.TemplateResponse(
        request=request, 
        name="index.html",
        context={
            "request": request, 
            "csrf_token": csrf_token,
            "brand_name": BRAND_NAME,
            "items": items_with_serials, 
            "current_category": category,
            "current_status": status,
            "expiry_days": expiry_days,
            "count_posted": count_posted,
            "count_partially_posted": count_partially_posted,
            "count_sold": count_sold,
            "count_pending": count_pending,
            "count_scheduled": count_scheduled,
            "count_pending_verifications": count_pending_verifications,
            "count_pending_reports": count_pending_reports,
            "count_orders": count_orders,
            "recent_orders": recent_orders,
            "sold_rate": sold_rate,
            "count_searches": count_searches,
            "count_active_sellers": count_active_sellers,
            "count_approved_sellers": count_approved_sellers,
            "category_breakdown": category_breakdown
        }
    )

@app.get("/inventory")
@app.get("/admin/inventory")
async def master_inventory(request: Request):
    session_token = get_auth_token(request)
    if not session_token:
        return RedirectResponse(url="/login", status_code=303)
    csrf_token = get_csrf_token(session_token)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Item).order_by(Item.id.desc()))
        items = result.scalars().all()
        
        inventory = []
        for item in items:
            inventory.append({
                "item": item,
                "serial": get_item_serial(item)
            })
            
    return templates.TemplateResponse(
        request=request,
        name="inventory.html",
        context={"request": request, "csrf_token": csrf_token, "brand_name": BRAND_NAME, "inventory": inventory}
    )

@app.get("/photo/{file_id}")
async def get_photo(file_id: str):
    import io
    from fastapi.responses import StreamingResponse, FileResponse
    
    try:
        if file_id.startswith("local:"):
            filename = file_id.replace("local:", "")
            filepath = os.path.join("uploads", filename)
            if os.path.exists(filepath):
                with open(filepath, "rb") as f:
                    return StreamingResponse(io.BytesIO(f.read()), media_type="image/jpeg")
            return FileResponse("static/placeholder.svg", media_type="image/svg+xml")
                    
        file = await bot.get_file(file_id)
        photo_bytes = await bot.download_file(file.file_path)
        return StreamingResponse(io.BytesIO(photo_bytes.read()), media_type="image/jpeg")
    except Exception as e:
        logger.debug(f"Photo retrieval fallback for {file_id}: {e}")
        return FileResponse("static/placeholder.svg", media_type="image/svg+xml")

@app.post("/action/post")
async def post_item(
    request: Request,
    item_id: int = Form(...),
    new_category: str = Form(...),
    csrf_token: str = Form("")
):
    verify_form_csrf(request, csrf_token)
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Item).where(Item.id == item_id))
            item = result.scalar_one_or_none()
            
            if not item or item.status not in (ItemStatus.PENDING, ItemStatus.PARTIALLY_POSTED):
                return RedirectResponse(url="/admin", status_code=303)
                
            # If category changed or sequence is not assigned, compute MAX(category_id_seq) + 1 inside transaction
            if item.category != new_category or not item.category_id_seq:
                item.category = new_category
                cat_max_res = await session.execute(
                    select(func.max(Item.category_id_seq)).where(Item.category == new_category)
                )
                max_val = cat_max_res.scalar()
                item.category_id_seq = (max_val or 0) + 1
            
            main_id, cat_id, errors = await publish_item_to_telegram(item)
            if main_id:
                item.channel_message_id = main_id
            if cat_id:
                item.category_message_id = cat_id

            expected_channels = 2 if (item.category_chat_id and item.category_chat_id != item.channel_chat_id) else 1
            posted_channels = (1 if item.channel_message_id else 0) + (1 if item.category_message_id else 0)

            if posted_channels >= expected_channels:
                item.status = ItemStatus.POSTED
                item.post_error = None
                logger.info(f"Item {item.id} fully posted to all {expected_channels} channels.")
                asyncio.create_task(check_search_alerts(item, bot))
            elif posted_channels > 0:
                item.status = ItemStatus.PARTIALLY_POSTED
                err_desc = "; ".join([f"{ch}: {err}" for ch, err in errors.items()])
                item.post_error = err_desc or "Partial failure: one channel failed to post."
                logger.warning(f"Item {item.id} partially posted: {item.post_error}")
            else:
                item.status = ItemStatus.PARTIALLY_POSTED
                err_desc = "; ".join([f"{ch}: {err}" for ch, err in errors.items()])
                item.post_error = f"Publish failed on all channels: {err_desc}"
                logger.error(f"Item {item.id} completely failed to publish: {item.post_error}")

            await session.commit()
            
        return RedirectResponse(url="/admin", status_code=303)
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.error(f"Error posting item: {trace}")
        return HTMLResponse(content=f"<html><body style='background:#111;color:red;'><pre>{trace}</pre></body></html>", status_code=500)

@app.post("/action/retry_post")
async def retry_post(
    request: Request,
    item_id: int = Form(...),
    csrf_token: str = Form("")
):
    verify_form_csrf(request, csrf_token)
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Item).where(Item.id == item_id))
            item = result.scalar_one_or_none()
            if not item:
                return RedirectResponse(url="/admin", status_code=303)

            main_channel = item.channel_chat_id or CHANNEL_ID
            cat_channel = item.category_chat_id or CATEGORY_CHANNELS.get(item.category)
            item.channel_chat_id = main_channel
            item.category_chat_id = cat_channel

            channels_to_retry = []
            if not item.channel_message_id:
                channels_to_retry.append(main_channel)
            if cat_channel and cat_channel != main_channel and not item.category_message_id:
                channels_to_retry.append(cat_channel)

            if not channels_to_retry:
                item.status = ItemStatus.POSTED
                item.post_error = None
                await session.commit()
                return RedirectResponse(url="/admin", status_code=303)

            logger.info(f"Retrying publishing for item {item.id} on channels: {channels_to_retry}")
            main_id, cat_id, errors = await publish_item_to_telegram(item, target_channels=channels_to_retry)
            if main_id:
                item.channel_message_id = main_id
            if cat_id:
                item.category_message_id = cat_id

            expected_channels = 2 if (cat_channel and cat_channel != main_channel) else 1
            posted_channels = (1 if item.channel_message_id else 0) + (1 if item.category_message_id else 0)

            if posted_channels >= expected_channels:
                item.status = ItemStatus.POSTED
                item.post_error = None
                logger.info(f"Item {item.id} retry successful: now fully POSTED.")
                asyncio.create_task(check_search_alerts(item, bot))
            else:
                item.status = ItemStatus.PARTIALLY_POSTED
                err_desc = "; ".join([f"{ch}: {err}" for ch, err in errors.items()])
                item.post_error = err_desc or "Retry partially failed."
                logger.warning(f"Item {item.id} retry incomplete: {item.post_error}")

            await session.commit()
        return RedirectResponse(url="/admin", status_code=303)
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.error(f"Error retrying post for item {item_id}: {trace}")
        return HTMLResponse(content=f"<html><body style='background:#111;color:red;'><pre>{trace}</pre></body></html>", status_code=500)

@app.post("/action/run_cleanup")
async def trigger_cleanup(request: Request, csrf_token: str = Form("")):
    verify_form_csrf(request, csrf_token)
    stats = await run_expiry_cleanup()
    logger.info(f"Manual expiry cleanup triggered by admin: {stats}")
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/action/sold")
async def mark_sold(request: Request, item_id: int = Form(...), csrf_token: str = Form("")):
    verify_form_csrf(request, csrf_token)
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Item).where(Item.id == item_id))
            item = result.scalar_one_or_none()
            
            if not item or item.status not in (ItemStatus.POSTED, ItemStatus.PARTIALLY_POSTED):
                return RedirectResponse(url="/admin", status_code=303)
                
            target_main = item.channel_chat_id or CHANNEL_ID
            target_cat = item.category_chat_id or CATEGORY_CHANNELS.get(item.category)
            
            if item.channel_message_id or item.category_message_id:
                original_caption = get_caption(item)
                new_caption = "❌ <b>ተሽጧል (SOLD)</b>\n\n" + original_caption
                
                if item.channel_message_id:
                    try:
                        await safe_telegram_call(lambda: bot.edit_message_caption(
                            chat_id=target_main,
                            message_id=item.channel_message_id,
                            caption=new_caption,
                            parse_mode="HTML"
                        ))
                    except Exception as e:
                        logger.warning(f"Error editing sold caption on main channel {target_main}: {e}")
                
                if item.category_message_id and target_cat:
                    try:
                        await safe_telegram_call(lambda: bot.edit_message_caption(
                            chat_id=target_cat,
                            message_id=item.category_message_id,
                            caption=new_caption,
                            parse_mode="HTML"
                        ))
                    except Exception as e:
                        logger.warning(f"Error editing sold caption in category channel {target_cat}: {e}")
                
                # For SOLD post, we just use the first photo
                first_photo = (item.photo_file_id or "").split(",")[0]
                if first_photo:
                    try:
                        if first_photo.startswith("local:"):
                            filename = first_photo.replace("local:", "")
                            filepath = os.path.join("uploads", filename)
                            with open(filepath, "rb") as f:
                                raw_bytes = f.read()
                        else:
                            file = await safe_telegram_call(lambda: bot.get_file(first_photo))
                            photo_bytes = await safe_telegram_call(lambda: bot.download_file(file.file_path))
                            raw_bytes = photo_bytes.read()
                            
                        watermarked_bytes = apply_watermark(raw_bytes)
                        
                        if item.channel_message_id:
                            try:
                                await safe_telegram_call(lambda: bot.send_photo(
                                    chat_id=target_main,
                                    photo=BufferedInputFile(watermarked_bytes, filename="watermarked.jpg"),
                                    caption=get_sold_caption(item),
                                    parse_mode="HTML"
                                ))
                            except Exception as e:
                                logger.warning(f"Error posting sold photo to main channel {target_main}: {e}")
                        
                        if item.category_message_id and target_cat:
                            try:
                                await safe_telegram_call(lambda: bot.send_photo(
                                    chat_id=target_cat,
                                    photo=BufferedInputFile(watermarked_bytes, filename="watermarked.jpg"),
                                    caption=get_sold_caption(item),
                                    parse_mode="HTML"
                                ))
                            except Exception as e:
                                logger.warning(f"Error posting sold image in category channel {target_cat}: {e}")
                    except Exception as e:
                        logger.warning(f"Error preparing sold photo for item {item.id}: {e}")
                            
            item.status = ItemStatus.SOLD
            item.post_error = None
            await session.commit()
            
        return RedirectResponse(url="/admin", status_code=303)
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.error(f"Error marking sold: {trace}")
        return HTMLResponse(content=f"<html><body style='background:#111;color:red;'><pre>{trace}</pre></body></html>", status_code=500)

@app.post("/action/delete")
async def delete_item(request: Request, item_id: int = Form(...), csrf_token: str = Form("")):
    verify_form_csrf(request, csrf_token)
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Item).where(Item.id == item_id))
            item = result.scalar_one_or_none()
            if item:
                target_main = item.channel_chat_id or CHANNEL_ID
                target_cat = item.category_chat_id or CATEGORY_CHANNELS.get(item.category)
                
                if item.channel_message_id and item.status != ItemStatus.PENDING:
                    try:
                        await bot.delete_message(chat_id=target_main, message_id=item.channel_message_id)
                    except Exception as e:
                        logger.warning(f"Error deleting message from Telegram ({target_main}): {e}")
                    
                    if item.category_message_id and target_cat:
                        try:
                            await bot.delete_message(chat_id=target_cat, message_id=item.category_message_id)
                        except Exception as e:
                            logger.warning(f"Error deleting category message ({target_cat}): {e}")
                
                await session.delete(item)
                await session.commit()
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.error(f"Error deleting item: {trace}")
        return HTMLResponse(content=f"<html><body style='background:#111;color:red;'><pre>{trace}</pre></body></html>", status_code=500)
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/action/edit")
async def edit_item(
    request: Request,
    item_id: int = Form(...),
    name: str = Form(...),
    price: str = Form(...),
    city: str = Form(...),
    place: str = Form(...),
    phone: str = Form(...),
    condition: str = Form(...),
    category: str = Form(...),
    username: str = Form(""),
    csrf_token: str = Form("")
):
    verify_form_csrf(request, csrf_token)
    if username is None: username = ""
    location = f"({city}) {place}"
    
    # Strip URLs and usernames from the item name
    name = re.sub(r'(?i)\b(?:https?://|www\.|t\.me/)\S+|@\S+', '', name).strip()
    name = re.sub(r'[\-\s]+$', '', name)

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Item).where(Item.id == item_id))
            item = result.scalar_one_or_none()
            
            if item:
                item.name = name
                item.price = price
                item.location = location
                item.phone = phone
                item.condition = condition
                item.category = category
                item.username = username
                
                target_main = item.channel_chat_id or CHANNEL_ID
                target_cat = item.category_chat_id or CATEGORY_CHANNELS.get(item.category)
                
                if item.status != ItemStatus.PENDING and item.channel_message_id:
                    new_caption = get_caption(item)
                    if item.status == ItemStatus.SOLD:
                        new_caption = "❌ <b>ተሽጧል (SOLD)</b>\n\n" + new_caption
                        
                    try:
                        await bot.edit_message_caption(
                            chat_id=target_main,
                            message_id=item.channel_message_id,
                            caption=new_caption,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Error editing live post caption in main channel {target_main}: {e}")
                        
                    if item.category_message_id and target_cat:
                        try:
                            await bot.edit_message_caption(
                                chat_id=target_cat,
                                message_id=item.category_message_id,
                                caption=new_caption,
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.warning(f"Error editing live post caption in category channel {target_cat}: {e}")
                
                await session.commit()
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.error(f"Error editing item: {trace}")
        return HTMLResponse(content=f"<html><body style='background:#111;color:red;'><pre>{trace}</pre></body></html>", status_code=500)
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/action/bump")
async def bump_item(request: Request, item_id: int = Form(...), csrf_token: str = Form("")):
    verify_form_csrf(request, csrf_token)
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Item).where(Item.id == item_id))
            item = result.scalar_one_or_none()
            if not item or item.status not in (ItemStatus.POSTED, ItemStatus.PARTIALLY_POSTED):
                return RedirectResponse(url="/admin", status_code=303)
                
            target_main = item.channel_chat_id or CHANNEL_ID
            target_cat = item.category_chat_id or CATEGORY_CHANNELS.get(item.category)
            
            # Attempt to delete old post
            if item.channel_message_id:
                try:
                    await safe_telegram_call(lambda: bot.delete_message(chat_id=target_main, message_id=item.channel_message_id))
                except Exception as e:
                    logger.warning(f"Bump: Could not delete old main message from Telegram: {e}")
                    
                if item.category_message_id and target_cat:
                    try:
                        await safe_telegram_call(lambda: bot.delete_message(chat_id=target_cat, message_id=item.category_message_id))
                    except Exception as e:
                        logger.warning(f"Bump: Could not delete old category message from Telegram: {e}")
            
            # Now build and post again
            new_main_id, new_cat_id, errors = await publish_item_to_telegram(item)
            
            # BUG D FIX: Never overwrite stored message_id with None on failed bump!
            if new_main_id:
                item.channel_message_id = new_main_id
            if new_cat_id:
                item.category_message_id = new_cat_id
                
            expected_channels = 2 if (target_cat and target_cat != target_main) else 1
            posted_channels = (1 if item.channel_message_id else 0) + (1 if item.category_message_id else 0)

            if posted_channels >= expected_channels:
                item.status = ItemStatus.POSTED
                item.post_error = None
            else:
                item.status = ItemStatus.PARTIALLY_POSTED
                err_desc = "; ".join([f"{ch}: {err}" for ch, err in errors.items()])
                item.post_error = err_desc or "Partial bump failure"

            await session.commit()
            
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.error(f"Error bumping item: {trace}")
        return HTMLResponse(content=f"<html><body style='background:#111;color:red;'><pre>{trace}</pre></body></html>", status_code=500)
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/action/schedule")
async def schedule_item(
    request: Request,
    item_id: int = Form(...),
    scheduled_time: str = Form(...),
    new_category: str = Form(None),
    csrf_token: str = Form("")
):
    verify_form_csrf(request, csrf_token)
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Item).where(Item.id == item_id))
            item = result.scalar_one_or_none()
            if item and item.status == ItemStatus.PENDING:
                if new_category:
                    item.category = new_category
                
                # Flexible parsing for datetime-local
                st = None
                for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        st = datetime.strptime(scheduled_time, fmt)
                        break
                    except ValueError:
                        continue
                
                if not st:
                    return HTMLResponse(content="Invalid datetime format from browser.", status_code=400)
                
                item.status = ItemStatus.SCHEDULED
                item.scheduled_time = st
                await session.commit()
                logger.info(f"Manual Action: Scheduled item {item.id} for {st}")
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.error(f"Error scheduling item: {trace}")
        return HTMLResponse(content=f"<html><body style='background:#111;color:red;'><pre>{trace}</pre></body></html>", status_code=500)
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/action/unschedule")
async def unschedule_item(request: Request, item_id: int = Form(...), csrf_token: str = Form("")):
    verify_form_csrf(request, csrf_token)
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Item).where(Item.id == item_id))
            item = result.scalar_one_or_none()
            if item and item.status == ItemStatus.SCHEDULED:
                item.status = ItemStatus.PENDING
                item.scheduled_time = None
                await session.commit()
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.error(f"Error unscheduling item: {trace}")
        return HTMLResponse(content=f"<html><body style='background:#111;color:red;'><pre>{trace}</pre></body></html>", status_code=500)
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/action/broadcast")
async def broadcast_message(request: Request, message: str = Form(...), csrf_token: str = Form("")):
    verify_form_csrf(request, csrf_token)
    try:
        channel_user = CHANNEL_ID.replace('@', '')
        header = f"📢 <b>{BRAND_NAME} — Administrative Announcement</b>\n" + "━" * 20 + "\n\n"
        full_text = header + message + "\n\n" + "━" * 20 + f"\n@{channel_user}"
        
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=full_text,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Broadcast failed: {e}")
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/action/post_welcome")
async def post_welcome(request: Request, csrf_token: str = Form("")):
    verify_form_csrf(request, csrf_token)
    try:
        welcome_text = (
            f"እንኳን ወደ {BRAND_NAME} ቻናል በደህና መጡ!\n\n"
            "ይህ ቻናል እቃ ለመግዛት፣ ለመሸጥ እና ለመግባባት ቀላል እና የታመነ መድረክ ነው።\n\n"
            "🛒 <b>ከእኛ የሚያገኙት:</b>\n"
            "• የተለያዩ እቃዎች (ስልኮች፣ መኪና፣ ቤት፣ ልብስ፣ ኮስሞቲክስ እና ፈርኒቸር)\n"
            "• ቀላል እና ፈጣን የግዢ እና የሽያጭ ሂደት\n"
            "• በAdmin የተረጋገጡ ፖስቶች\n\n"
            "📩 <b>ለመሸጥ:</b>\n"
            "እቃዎን በፎቶ፣ ዋጋ እና አድራሻ ከላኩልን በኋላ እኛ በቻናሉ ላይ እናስቀምጣለን።\n\n"
            "🤝 <b>ለመግዛት:</b>\n"
            "በፖስቱ ላይ ያለውን ኮንታክት ተጠቅመው በቀጥታ ከሻጭ ጋር ይገናኙ።\n\n"
            "📣 ቻናሉን ለጓደኞቻችሁ እና ለቤተሰቦቻችሁ ያጋሩ\n"
            "➡️ ብዙ ሰዎች = ፈጣን ሽያጭ\n\n"
            f"⚡ <b>{BRAND_NAME} — ፈጣን፣ ቀላል፣ የታመነ!</b>"
        )
        
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=welcome_text,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Welcome message failed: {e}")
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/action/post_recap")
async def post_daily_recap(request: Request, csrf_token: str = Form("")):
    verify_form_csrf(request, csrf_token)
    try:
        async with AsyncSessionLocal() as session:
            # Items posted in the last 24 hours (using timezone-aware utc)
            threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
            result = await session.execute(
                select(Item).where(Item.status == ItemStatus.POSTED, Item.created_at >= threshold)
            )
            recent_items = result.scalars().all()
            
            if not recent_items:
                return RedirectResponse(url="/admin", status_code=303)
                
            recap_text = f"📈 <b>{BRAND_NAME} DAILY RECAP: NEW LISTINGS</b>\n"
            recap_text += f"<i>{datetime.now().strftime('%B %d, %Y')}</i>\n"
            recap_text += "━" * 15 + "\n\n"
            
            channel_user = CHANNEL_ID.replace("@", "")
            
            for idx, item in enumerate(recent_items, 1):
                item_link = f"https://t.me/{channel_user}/{item.channel_message_id}" if item.channel_message_id else f"https://t.me/{channel_user}"
                recap_text += f"{idx}. <b>{item.name}</b>\n"
                recap_text += f"   💰 {item.price}\n"
                recap_text += f"   🔗 <a href='{item_link}'>View Details</a>\n\n"
                
            recap_text += "━" * 15 + "\n"
            recap_text += f"👉 Join @{channel_user} for more!"
            
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=recap_text,
                parse_mode="HTML",
                disable_web_page_preview=False
            )
    except Exception as e:
        logger.error(f"Recap failed: {e}")
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/action/import_telegram")
async def import_telegram_post(request: Request, url: str = Form(...)):
    session_token = get_auth_token(request)
    if not session_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        filenames = await scrape_telegram_photos(url)
        return {"filenames": filenames}
    except Exception as e:
        return {"error": str(e)}, 500

@app.post("/settings/update")
async def update_settings(request: Request, expiry_days: int = Form(...), csrf_token: str = Form("")):
    verify_form_csrf(request, csrf_token)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Settings).limit(1))
        settings = result.scalar_one_or_none()
        if settings:
            settings.expiry_days = expiry_days
            await session.commit()
            
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/action/add_item")
async def add_item_web(
    request: Request,
    name: str = Form(...),
    price: str = Form(...),
    city: str = Form(...),
    place: str = Form(...),
    phone: str = Form(...),
    condition: str = Form(...),
    category: str = Form(...),
    username: str = Form(""),
    photos: list[UploadFile] = File(...),
    csrf_token: str = Form("")
):
    verify_form_csrf(request, csrf_token)
    if username is None: username = ""
    location = f"({city}) {place}"
    
    # Strip URLs and usernames from the item name
    name = re.sub(r'(?i)\b(?:https?://|www\.|t\.me/)\S+|@\S+', '', name).strip()
    name = re.sub(r'[\-\s]+$', '', name)

    try:
        saved_ids = []
        for photo in photos:
            content = await photo.read()
            # Validate image magic bytes
            if not is_valid_image(content):
                return HTMLResponse(
                    content=f"<html><body style='background:#111;color:red;'><h3>Invalid Image Upload</h3><p>File '{photo.filename}' is not a valid JPEG, PNG, WEBP, or GIF image.</p><a href='/'>Go Back</a></body></html>",
                    status_code=400
                )
            ext = photo.filename.split(".")[-1].lower() if "." in photo.filename else "jpg"
            filename = f"{uuid.uuid4()}.{ext}"
            filepath = os.path.join("uploads", filename)
            
            with open(filepath, "wb") as f:
                f.write(content)
            saved_ids.append(f"local:{filename}")
            
        async with AsyncSessionLocal() as session:
            # BUG C FIX: Calculate category sequence number with MAX(category_id_seq) + 1 inside transaction
            cat_max_res = await session.execute(
                select(func.max(Item.category_id_seq)).where(Item.category == category)
            )
            max_val = cat_max_res.scalar()
            cat_seq = (max_val or 0) + 1
            
            new_item = Item(
                photo_file_id=",".join(saved_ids),
                name=name,
                price=price,
                location=location,
                phone=phone,
                condition=condition,
                username=username,
                category=category,
                category_id_seq=cat_seq,
                status=ItemStatus.PENDING,
                channel_message_id=None
            )
            session.add(new_item)
            await session.commit()
            
        return RedirectResponse(url="/admin", status_code=303)
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.error(f"Error adding item: {trace}")
        return HTMLResponse(content=f"<html><body style='background:#111;color:red;'><pre>{trace}</pre></body></html>", status_code=500)

@app.get("/health")
async def health_check():
    """
    Health check endpoint reporting database connectivity, background task states,
    and marketplace inventory metrics.
    """
    health_data = {
        "status": "healthy",
        "brand": BRAND_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {"status": "ok", "error": None, "stats": {}},
        "background_tasks": {},
        "system": {
            "host": SERVER_HOST,
            "port": SERVER_PORT
        }
    }
    status_code = 200

    # 1. Check Database Connectivity & Metrics
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            posted_res = await session.execute(select(func.count(Item.id)).where(Item.status == ItemStatus.POSTED))
            partial_res = await session.execute(select(func.count(Item.id)).where(Item.status == ItemStatus.PARTIALLY_POSTED))
            pending_res = await session.execute(select(func.count(Item.id)).where(Item.status == ItemStatus.PENDING))
            health_data["database"]["stats"] = {
                "posted": posted_res.scalar() or 0,
                "partially_posted": partial_res.scalar() or 0,
                "pending": pending_res.scalar() or 0
            }
    except Exception as e:
        health_data["status"] = "unhealthy"
        health_data["database"]["status"] = "error"
        health_data["database"]["error"] = str(e)
        status_code = 503

    # 2. Check Background Task Lifecycle States
    for name, task in background_tasks.items():
        if task is None:
            health_data["background_tasks"][name] = "not_started"
        elif task.done():
            if task.cancelled():
                health_data["background_tasks"][name] = "cancelled"
            elif task.exception():
                health_data["background_tasks"][name] = f"crashed: {task.exception()}"
                if health_data["status"] == "healthy":
                    health_data["status"] = "degraded"
            else:
                health_data["background_tasks"][name] = "completed"
        else:
            health_data["background_tasks"][name] = "running"

    return JSONResponse(content=health_data, status_code=status_code)

# ── Step 5 Trust & Verification Endpoints ─────────────────────────────────

@app.post("/action/toggle_verify")
async def toggle_item_verify(request: Request, item_id: int = Form(...), csrf_token: str = Form("")):
    verify_form_csrf(request, csrf_token)
    async with AsyncSessionLocal() as session:
        item = await session.get(Item, item_id)
        if item:
            item.is_verified = 0 if item.is_verified else 1
            await session.commit()
            
            # If item is posted, update channel caption to reflect verified status
            if item.status == ItemStatus.POSTED:
                new_caption = get_caption(item)
                if item.channel_chat_id and item.channel_message_id:
                    try:
                        await safe_telegram_call(lambda: bot.edit_message_caption(
                            chat_id=item.channel_chat_id,
                            message_id=item.channel_message_id,
                            caption=new_caption,
                            parse_mode="HTML"
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to update channel caption on toggle verify: {e}")
                if item.category_chat_id and item.category_message_id and item.category_chat_id != item.channel_chat_id:
                    try:
                        await safe_telegram_call(lambda: bot.edit_message_caption(
                            chat_id=item.category_chat_id,
                            message_id=item.category_message_id,
                            caption=new_caption,
                            parse_mode="HTML"
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to update category caption on toggle verify: {e}")

    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/verifications")
async def list_verifications(request: Request):
    session_token = get_auth_token(request)
    if not session_token:
        return RedirectResponse(url="/login", status_code=303)
    csrf_token = get_csrf_token(session_token)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Seller).order_by(Seller.id.desc()))
        sellers = result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="verifications.html",
        context={"request": request, "csrf_token": csrf_token, "brand_name": BRAND_NAME, "sellers": sellers}
    )

@app.post("/action/verify_seller")
async def action_verify_seller(
    request: Request,
    seller_id: int = Form(...),
    decision: str = Form(...),
    reason: str = Form(""),
    csrf_token: str = Form("")
):
    verify_form_csrf(request, csrf_token)
    async with AsyncSessionLocal() as session:
        seller = await session.get(Seller, seller_id)
        if seller:
            seller.reviewed_at = datetime.utcnow()
            if decision == "approve":
                seller.status = "approved"
                seller.rejection_reason = None
                items_res = await session.execute(
                    select(Item).where(
                        or_(
                            Item.telegram_user_id == seller.telegram_user_id,
                            Item.username.ilike(seller.username or "__none__")
                        )
                    )
                )
                for it in items_res.scalars().all():
                    it.is_verified = 1
                
                try:
                    await bot.send_message(
                        chat_id=seller.telegram_user_id,
                        text=(
                            f"🎉 <b>እንኳን ደስ አለዎት! / Congratulations!</b>\n\n"
                            f"የ {BRAND_NAME} ሻጭ መለያዎ ተረጋግጧል (Verified Seller)።\n"
                            "ከአሁን በኋላ የሚለጥፏቸው እቃዎች ሁሉ '✅ የተረጋገጠ ሻጭ' የሚል ምልክት ይኖራቸዋል።"
                        ),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Could not notify seller {seller.telegram_user_id}: {e}")

            elif decision == "reject":
                seller.status = "rejected"
                seller.rejection_reason = reason or "Verification requirements not met."
                try:
                    await bot.send_message(
                        chat_id=seller.telegram_user_id,
                        text=(
                            f"⚠️ <b>የሻጭ ማረጋገጫ ማመልከቻ / Seller Verification Notice</b>\n\n"
                            f"ማመልከቻዎ በሚከተለው ምክንያት ውድቅ ተደርጓል:\n<i>{html.escape(seller.rejection_reason)}</i>\n\n"
                            "ትክክለኛ መረጃ በመያዝ በድጋሚ ማመልከት ይችላሉ።"
                        ),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Could not notify seller {seller.telegram_user_id}: {e}")

            await session.commit()

    return RedirectResponse(url="/admin/verifications", status_code=303)

@app.get("/admin/id_photo/{filename}")
async def view_id_photo(request: Request, filename: str):
    session_token = get_auth_token(request)
    if not session_token:
        return HTMLResponse("Unauthorized", status_code=401)
    safe_name = os.path.basename(filename)
    filepath = os.path.join("secure_uploads", "ids", safe_name)
    if os.path.exists(filepath):
        return FileResponse(filepath)
    return HTMLResponse("ID photo document not found", status_code=404)

@app.get("/admin/reports")
async def list_reports(request: Request):
    session_token = get_auth_token(request)
    if not session_token:
        return RedirectResponse(url="/login", status_code=303)
    csrf_token = get_csrf_token(session_token)

    async with AsyncSessionLocal() as session:
        reports_res = await session.execute(select(Report).order_by(Report.id.desc()))
        reports = reports_res.scalars().all()

        reports_with_items = []
        for rep in reports:
            item = await session.get(Item, rep.item_id)
            reports_with_items.append({"report": rep, "item": item})

    return templates.TemplateResponse(
        request=request,
        name="reports.html",
        context={"request": request, "csrf_token": csrf_token, "brand_name": BRAND_NAME, "reports": reports_with_items}
    )

@app.post("/action/resolve_report")
async def action_resolve_report(
    request: Request,
    report_id: int = Form(...),
    action_type: str = Form(...),
    csrf_token: str = Form("")
):
    verify_form_csrf(request, csrf_token)
    async with AsyncSessionLocal() as session:
        report = await session.get(Report, report_id)
        if report:
            if action_type == "dismiss":
                report.status = "dismissed"
            elif action_type == "delete_item":
                report.status = "resolved"
                item = await session.get(Item, report.item_id)
                if item:
                    if item.channel_chat_id and item.channel_message_id:
                        try:
                            await safe_telegram_call(lambda: bot.delete_message(
                                chat_id=item.channel_chat_id,
                                message_id=item.channel_message_id
                            ))
                        except Exception:
                            pass
                    if item.category_chat_id and item.category_message_id and item.category_chat_id != item.channel_chat_id:
                        try:
                            await safe_telegram_call(lambda: bot.delete_message(
                                chat_id=item.category_chat_id,
                                message_id=item.category_message_id
                            ))
                        except Exception:
                            pass
                    await session.delete(item)
            await session.commit()

    return RedirectResponse(url="/admin/reports", status_code=303)

@app.post("/action/run_backup")
async def action_run_backup(request: Request, csrf_token: str = Form("")):
    verify_form_csrf(request, csrf_token)
    backup_file = await run_sqlite_backup()
    referer = request.headers.get("referer") or "/"
    return RedirectResponse(url=referer, status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=SERVER_HOST, port=SERVER_PORT, reload=True)

