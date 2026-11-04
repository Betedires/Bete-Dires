"""
telegram_forwarder/bot.py
Bete Dires (ቤተ ድረስ) Telethon Userbot Forwarder — Step 6

Improvements over previous version:
- PARTIALLY_POSTED status when main channel succeeds but category channel fails
- Startup catchup: replays messages missed while the bot was down (configurable)
- Configurable confidence threshold via CONFIDENCE_MODE env var ('strict'/'relaxed')
- Configurable MAX_FLOOD_WAIT_SECONDS (default 60)
- Never overwrites a stored message_id with None on failure
"""
import os
import sys
import asyncio
import logging
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, RPCError
from dotenv import load_dotenv

# Ensure root directory is on sys.path so we can import shared modules
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Load environment variables: forwarder-specific .env first, then root .env
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# Import database and shared configuration
from database import AsyncSessionLocal, Item, ItemStatus
from config import (
    CATEGORY_CHANNELS,
    CHANNEL_ID,
    BRAND_HASHTAG,
    WATERMARK_TEXT
)
from sqlalchemy import select, func

# Import custom forwarder modules
from parser import (
    parse_source_text,
    format_target_text,
    detect_category,
    evaluate_confidence,
    compute_content_hash
)
from id_manager import format_serial, get_next_category_sequence
from image_utils import add_watermark

# ── Structured Logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s'
)
logger = logging.getLogger("BeteDires_Forwarder")

# ── Core Config ─────────────────────────────────────────────────────────────
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Source groups: support comma-separated list in SOURCE_GROUPS or single SOURCE_GROUP
raw_sources = os.getenv("SOURCE_GROUPS") or os.getenv("SOURCE_GROUP", "")
SOURCE_GROUPS = [s.strip() for s in raw_sources.split(",") if s.strip()]

# Target group: defaults to CHANNEL_ID from config if not explicitly set
TARGET_GROUP = os.getenv("TARGET_GROUP", CHANNEL_ID)

# Flood-wait cap: max seconds to wait before giving up on a Telegram API call
MAX_FLOOD_WAIT = int(os.getenv("MAX_FLOOD_WAIT_SECONDS", "60"))

# Confidence mode: "strict" (item+price+phone required), "relaxed" (item + price OR phone)
CONFIDENCE_MODE = os.getenv("CONFIDENCE_MODE", "strict").lower()

# Whether to replay missed messages on startup (set false to disable catchup)
ENABLE_CATCHUP = os.getenv("ENABLE_CATCHUP", "true").lower() == "true"

if not all([API_ID, API_HASH, SOURCE_GROUPS, TARGET_GROUP]):
    logger.error("Please ensure API_ID, API_HASH, SOURCE_GROUP(S), and TARGET_GROUP are configured.")
    sys.exit(1)


# ── Helpers ──────────────────────────────────────────────────────────────────
def normalize_group_id(gid: str):
    """Parses integer chat IDs (with -100 prefix) or returns username string."""
    gid = gid.strip()
    if (gid.startswith("-") and gid[1:].isdigit()) or gid.isdigit():
        return int(gid)
    return gid

RESOLVED_SOURCES = [normalize_group_id(s) for s in SOURCE_GROUPS]
RESOLVED_TARGET = normalize_group_id(TARGET_GROUP)

LAST_MESSAGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_message_id.txt")
UPLOADS_DIR = os.path.join(ROOT_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


def get_last_message_id() -> int | None:
    """Reads the last processed message ID from disk."""
    if os.path.exists(LAST_MESSAGE_FILE):
        with open(LAST_MESSAGE_FILE, "r") as f:
            content = f.read().strip()
            if content.isdigit():
                return int(content)
    return None


def save_last_message_id(message_id: int):
    """Persists the last processed message ID to disk."""
    with open(LAST_MESSAGE_FILE, "w") as f:
        f.write(str(message_id))


# ── Session Path (outside OneDrive sync) ─────────────────────────────────────
SESSION_DIR = os.getenv("SESSION_DIR")
if not SESSION_DIR:
    if sys.platform == "win32":
        base_dir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    else:
        base_dir = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    SESSION_DIR = os.path.join(base_dir, "BeteDiresBot")

os.makedirs(SESSION_DIR, exist_ok=True)
SESSION_PATH = os.path.join(SESSION_DIR, "userbot_session")

client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
client.parse_mode = 'html'


# ── Retry Wrappers ────────────────────────────────────────────────────────────
async def safe_download_media(message, file_path: str, max_retries: int = 3):
    """Downloads media with automatic FloodWait backoff."""
    for attempt in range(max_retries):
        try:
            return await message.download_media(file=file_path)
        except FloodWaitError as e:
            logger.warning(
                f"Telethon FloodWait downloading media: {e.seconds}s "
                f"(attempt {attempt+1}/{max_retries})"
            )
            if e.seconds > MAX_FLOOD_WAIT:
                logger.error(f"FloodWait {e.seconds}s exceeds cap {MAX_FLOOD_WAIT}s. Aborting.")
                raise
            await asyncio.sleep(e.seconds)
        except RPCError as e:
            logger.error(f"Telethon RPCError downloading media: {e}")
            raise


async def safe_send_file(target, file_path: str, caption: str, max_retries: int = 3):
    """Sends a file via Telethon with automatic FloodWait backoff."""
    for attempt in range(max_retries):
        try:
            return await client.send_file(target, file_path, caption=caption)
        except FloodWaitError as e:
            logger.warning(
                f"Telethon FloodWait sending to {target}: {e.seconds}s "
                f"(attempt {attempt+1}/{max_retries})"
            )
            if e.seconds > MAX_FLOOD_WAIT:
                logger.error(f"FloodWait {e.seconds}s exceeds cap {MAX_FLOOD_WAIT}s. Aborting send.")
                raise
            await asyncio.sleep(e.seconds)
        except RPCError as e:
            logger.error(f"Telethon RPCError sending to {target}: {e}")
            raise


# ── Configurable Confidence Evaluation ───────────────────────────────────────
def is_confident_enough(parsed_data: dict) -> tuple[bool, str]:
    """
    Evaluates confidence based on CONFIDENCE_MODE env var:
    - 'strict'  (default): item + valid price + valid phone all required
    - 'relaxed': item + (valid price OR valid phone) sufficient

    Returns (is_high_confidence: bool, reason: str).
    """
    import re
    item = parsed_data.get("item", "").strip()
    price = parsed_data.get("price", "").strip()
    phone = parsed_data.get("phone", "").strip()

    if not item or len(item) < 2:
        return False, "missing_item"

    has_price = (
        bool(price)
        and bool(re.search(r'\d', price))
        and price.lower() not in ("n/a", "none", "-")
    )
    phone_digits = re.sub(r'\D', '', phone)
    has_phone = bool(phone) and len(phone_digits) >= 9

    if CONFIDENCE_MODE == "relaxed":
        if has_price or has_phone:
            return True, "relaxed_confidence"
        return False, "missing_price_and_phone"
    else:  # strict (default)
        if not has_price:
            return False, "missing_or_invalid_price"
        if not has_phone:
            return False, "missing_or_invalid_phone"
        return True, "high_confidence"


# ── Source Link Builder ────────────────────────────────────────────────────────
def build_source_link(message) -> str:
    """Builds a clickable link back to the source message for admin reference."""
    try:
        chat = message.chat
        if getattr(chat, 'username', None):
            return f"https://t.me/{chat.username}/{message.id}"
        chat_id_str = str(message.chat_id).replace("-100", "").replace("-", "")
        return f"https://t.me/c/{chat_id_str}/{message.id}"
    except Exception:
        return f"chat_id:{message.chat_id}/msg:{message.id}"


# ── Core Message Processor ─────────────────────────────────────────────────────
async def process_message(message):
    """
    Processes a single forwarded message end-to-end:
    1. Skip if no text + photo.
    2. Deduplicate via SHA-256 content hash (normalized text + image).
    3. Parse fields (item name, price, phone, location, inbox, condition).
    4. Detect category. Evaluate confidence.
    5. Low confidence → save as PENDING draft for admin dashboard review.
    6. High confidence → allocate atomic serial, watermark image, post to channels.
    7. Partial failure (main ok, category fails) → PARTIALLY_POSTED status.
    8. Save all message IDs (never overwrite stored IDs with None on failure).
    """
    if not (message.text and message.photo):
        return

    logger.info(f"Processing source message ID {message.id} from chat {message.chat_id}")
    temp_download_path = f"temp_{message.id}.jpg"
    final_upload_path = None

    try:
        # Step 1: Download image to compute content hash
        await safe_download_media(message, file_path=temp_download_path)
        with open(temp_download_path, "rb") as f:
            image_bytes = f.read()

        # Step 2: Compute deduplication hash (normalized text + image bytes)
        content_hash = compute_content_hash(message.raw_text, image_bytes)

        # Step 3: Check DB for existing item with this content_hash
        async with AsyncSessionLocal() as session:
            existing = await session.scalar(
                select(Item).where(Item.content_hash == content_hash)
            )
            if existing:
                logger.info(
                    f"Duplicate detected (matches Item #{existing.id}, "
                    f"serial: {format_serial(existing.id, existing.category or 'Others', existing.category_id_seq or 0)}). "
                    f"Skipping repost."
                )
                return

        # Step 4: Parse and evaluate confidence
        parsed_data = parse_source_text(message.raw_text)
        detected_category = detect_category(message.raw_text, parsed_data.get("item", ""))
        is_high_conf, conf_reason = is_confident_enough(parsed_data)

        # Step 5: Save watermarked image to uploads/ with local: prefix
        saved_filename = f"fwd_{message.id}_{content_hash[:8]}.jpg"
        final_upload_path = os.path.join(UPLOADS_DIR, saved_filename)
        add_watermark(temp_download_path, output_path=final_upload_path)
        photo_ref = f"local:{saved_filename}"

        source_chat_str = str(message.chat_id)
        source_link = build_source_link(message)

        # Step 6: Low confidence → save as PENDING for admin review
        if not is_high_conf:
            logger.warning(
                f"Low-confidence parse for message {message.id} "
                f"(reason: {conf_reason}, mode: {CONFIDENCE_MODE}). Saving as PENDING draft."
            )
            async with AsyncSessionLocal() as session:
                new_item = Item(
                    photo_file_id=photo_ref,
                    name=parsed_data.get("item") or "Unparsed Forwarded Item",
                    price=parsed_data.get("price") or "N/A",
                    location=parsed_data.get("location") or "Gondar",
                    phone=parsed_data.get("phone") or "N/A",
                    condition=parsed_data.get("condition") or "ያገለገለ",
                    username=parsed_data.get("inbox", "").replace("@", ""),
                    category=detected_category,
                    category_id_seq=None,
                    status=ItemStatus.PENDING,
                    source_chat_id=source_chat_str,
                    source_message_id=message.id,
                    source_link=source_link,
                    content_hash=content_hash,
                    post_error=f"Low confidence ({CONFIDENCE_MODE}): {conf_reason}"
                )
                session.add(new_item)
                await session.commit()
                await session.refresh(new_item)
                logger.info(f"Created PENDING Item #{new_item.id} for admin moderation.")
            return

        # Step 7: High confidence → allocate atomic category sequence
        async with AsyncSessionLocal() as session:
            next_seq = await get_next_category_sequence(session, detected_category)
            new_item = Item(
                photo_file_id=photo_ref,
                name=parsed_data.get("item"),
                price=parsed_data.get("price"),
                location=parsed_data.get("location") or "Gondar",
                phone=parsed_data.get("phone"),
                condition=parsed_data.get("condition") or "ያገለገለ",
                username=parsed_data.get("inbox", "").replace("@", ""),
                category=detected_category,
                category_id_seq=next_seq,
                # Optimistic: set POSTED now; downgrade to PARTIALLY_POSTED if cat fails
                status=ItemStatus.POSTED,
                source_chat_id=source_chat_str,
                source_message_id=message.id,
                source_link=source_link,
                content_hash=content_hash
            )
            session.add(new_item)
            await session.commit()
            await session.refresh(new_item)
            item_id = new_item.id
            item_seq = new_item.category_id_seq
            serial = format_serial(item_id, detected_category, item_seq)

        caption = format_target_text(
            parsed_data,
            serial=serial,
            channel_handle=str(TARGET_GROUP),
            is_verified=False,
            category=detected_category,
            brand_hashtag=BRAND_HASHTAG
        )

        # Step 8: Post to main hub channel
        logger.info(f"Posting Item #{item_id} ({serial}) → main hub {RESOLVED_TARGET}...")
        sent_main = await safe_send_file(RESOLVED_TARGET, final_upload_path, caption=caption)
        main_msg_id = sent_main.id if sent_main else None

        # Step 9: Post to category channel (separate, optional)
        cat_channel_raw = CATEGORY_CHANNELS.get(detected_category)
        cat_msg_id = None
        cat_failed = False

        if cat_channel_raw and cat_channel_raw != TARGET_GROUP:
            resolved_cat = normalize_group_id(cat_channel_raw)
            try:
                logger.info(f"Posting Item #{item_id} → category channel {resolved_cat}...")
                sent_cat = await safe_send_file(resolved_cat, final_upload_path, caption=caption)
                cat_msg_id = sent_cat.id if sent_cat else None
            except Exception as e:
                logger.error(
                    f"Category channel post failed for Item #{item_id} "
                    f"→ {resolved_cat}: {e}"
                )
                cat_failed = True

        # Step 10: Save message IDs and final status back to DB
        # IMPORTANT: Never overwrite stored message_id with None on partial failure
        async with AsyncSessionLocal() as session:
            db_item = await session.get(Item, item_id)
            if db_item:
                db_item.channel_message_id = main_msg_id
                db_item.channel_chat_id = str(RESOLVED_TARGET)

                # Only store category IDs if the post actually succeeded
                if cat_msg_id is not None:
                    db_item.category_message_id = cat_msg_id
                    db_item.category_chat_id = str(cat_channel_raw)

                # Downgrade status if category post failed
                if cat_failed:
                    db_item.status = ItemStatus.PARTIALLY_POSTED
                    db_item.post_error = (
                        f"Main posted (msg_id:{main_msg_id}), "
                        f"category channel {cat_channel_raw} failed"
                    )
                    logger.warning(
                        f"Item #{item_id} marked PARTIALLY_POSTED. "
                        f"Use dashboard Retry button to complete posting."
                    )
                else:
                    db_item.status = ItemStatus.POSTED
                    db_item.post_error = None

                await session.commit()

        logger.info(
            f"Item #{item_id} ({serial}) complete — "
            f"main_msg_id={main_msg_id}, cat_msg_id={cat_msg_id}, "
            f"status={'PARTIALLY_POSTED' if cat_failed else 'POSTED'}."
        )

    except Exception as e:
        logger.error(f"Error processing message {message.id}: {e}", exc_info=True)
    finally:
        # Always clean up the temp download file
        if os.path.exists(temp_download_path):
            try:
                os.remove(temp_download_path)
            except Exception:
                pass


# ── Event Handler ─────────────────────────────────────────────────────────────
@client.on(events.NewMessage(chats=RESOLVED_SOURCES))
async def handler(event):
    """Triggered on every new message in any configured SOURCE_GROUPS."""
    await process_message(event.message)
    save_last_message_id(event.message.id)


# ── Catchup: Replay Missed Messages ──────────────────────────────────────────
async def catchup_missed_messages():
    """
    On startup, replays messages that arrived in each source group
    since the last recorded message ID (persisted in last_message_id.txt).
    This allows the forwarder to recover from downtime without missing listings.

    Controlled by ENABLE_CATCHUP env var (default: true).
    Deduplication via content hash prevents double-posting.
    """
    if not ENABLE_CATCHUP:
        logger.info("Catchup disabled (ENABLE_CATCHUP=false).")
        return

    last_id = get_last_message_id()
    if not last_id:
        logger.info("No last_message_id.txt — skipping catchup (processing only new messages).")
        return

    logger.info(f"Starting catchup from message ID {last_id} across {len(RESOLVED_SOURCES)} source(s)...")
    caught_up = 0

    for source in RESOLVED_SOURCES:
        try:
            async for message in client.iter_messages(source, min_id=last_id, reverse=True):
                if message.text and message.photo:
                    logger.info(f"[Catchup] Replaying message {message.id} from {source}...")
                    await process_message(message)
                    save_last_message_id(message.id)
                    caught_up += 1
                    await asyncio.sleep(1)  # Gentle pacing to avoid rate limits during catchup
        except Exception as e:
            logger.error(f"[Catchup] Error replaying messages from {source}: {e}")

    if caught_up:
        logger.info(f"Catchup complete: replayed {caught_up} missed message(s).")
    else:
        logger.info("Catchup complete: no missed messages found.")


# ── Entry Point ───────────────────────────────────────────────────────────────
async def main():
    logger.info("=" * 60)
    logger.info("Starting Bete Dires Telethon Userbot Forwarder")
    logger.info(f"  Source groups  : {RESOLVED_SOURCES}")
    logger.info(f"  Target channel : {RESOLVED_TARGET}")
    logger.info(f"  Confidence mode: {CONFIDENCE_MODE}")
    logger.info(f"  Catchup        : {ENABLE_CATCHUP}")
    logger.info(f"  Max flood wait : {MAX_FLOOD_WAIT}s")
    logger.info("=" * 60)

    await client.start()
    logger.info("Userbot connected to Telegram!")

    await catchup_missed_messages()

    logger.info("Listening for new messages...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
