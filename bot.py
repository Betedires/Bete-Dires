import os
import re
import html
import uuid
import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    ErrorEvent
)
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

from sqlalchemy import select, func, text, or_
from database import (
    AsyncSessionLocal,
    Item,
    ItemStatus,
    UserPreference,
    SearchAlert,
    Seller,
    Report
)
from config import (
    BOT_TOKEN,
    BRAND_NAME,
    CHANNEL_ID,
    CATEGORY_CHANNELS,
    ITEM_SHORTHANDS
)
from search_engine import (
    parse_search_query,
    execute_search,
    is_serial_number,
    parse_price_number
)
from captions import get_item_serial, get_sold_caption

logger = logging.getLogger("BeteDires_Bot")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Ephemeral in-memory cache for search results pagination (short_id -> list of item_ids)
search_cache: dict[str, dict] = {}

def prune_search_cache():
    if len(search_cache) > 200:
        keys_to_remove = list(search_cache.keys())[:50]
        for k in keys_to_remove:
            search_cache.pop(k, None)

# --- Bilingual Text Dictionary ---
MESSAGES = {
    "am": {
        "welcome": (
            f"እንኳን ወደ <b>{BRAND_NAME}</b> በደህና መጡ!\n\n"
            "የሚፈልጉትን እቃ በፍጥነት መፈለግ፣ በዘርፍ መቃኘት ወይም የሚሸጡትን እቃ በቀላሉ መለጠፍ ይችላሉ።"
        ),
        "btn_search": "🔍 እቃ ፈልግ",
        "btn_browse": "📂 በዘርፍ መርጥ",
        "btn_post": "➕ እቃ ለመሸጥ",
        "btn_my_listings": "📋 የእኔ እቃዎች",
        "btn_verify": "🛡 የሻጭ ማረጋገጫ",
        "btn_channels": "📢 ቻናሎች",
        "btn_lang_toggle": "🌐 English",
        "search_prompt": (
            "🔍 <b>የሚፈልጉትን እቃ ስም፣ ዋጋ፣ ከተማ ወይም መለያ ቁጥር ይጻፉ:</b>\n\n"
            "<i>ምሳሌዎች:</i>\n"
            "• <code>iphone 20000 Gondar</code>\n"
            "• <code>ሶፋ 15 ሺህ ባህር ዳር</code>\n"
            "• <code>050 EL 015</code> (በመለያ ቁጥር)"
        ),
        "no_results": "😔 <b>ምንም የሚዛመድ እቃ አልተገኘም።</b>\n\nይህ እቃ ሲፖሰት ወዲያውኑ መልዕክት እንዲደርስዎት ይፈልጋሉ?",
        "notify_btn": "🔔 አዲስ ሲገባ አሳውቀኝ (Notify Me)",
        "alert_saved": "✅ ማሳወቂያ ተመዝግቧል! የሚዛመድ እቃ ሲፖሰት ወዲያውኑ መልዕክት ይደርስዎታል።",
        "view_channel": "🔗 በቴሌግራም ቻናል ይመልከቱ",
        "browse_title": "📂 <b>የእቃውን ዘርፍ ይምረጡ:</b>",
        "my_listings_title": "📋 <b>የእርስዎ የተመዘገቡ እቃዎች:</b>\n\n",
        "no_listings": "እስካሁን ምንም የፖሰቱት እቃ የለም። እቃ ለመለጠፍ <b>➕ እቃ ለመሸጥ</b> የሚለውን ይጫኑ።",
        "channels_title": f"📢 <b>የ {BRAND_NAME} ይፋዊ ቻናሎች:</b>\n\nየተለያዩ እቃዎችን በቀጥታ በየዘርፋቸው ለመከታተል ሊንኮቹን ይጫኑ:\n\n",
        "photo_prompt": "እባክዎ የእቃውን ፎቶ ይላኩልን:",
        "name_prompt": "የእቃው አይነት (ስም) ያስገቡ:",
        "price_prompt": "የእቃው ዋጋ ስንት ነው?",
        "city_prompt": "ከተማ ይምረጡ (Choose City):",
        "place_prompt": "ልዩ ቦታ (Specific Place) ያስገቡ:\nምሳሌ: አራዳ ወይም ቦሌ",
        "phone_prompt": "የባለቤቱ ስልክ ቁጥር ያስገቡ:",
        "condition_prompt": "የእቃው ሁኔታ ምን ይመስላል? (አዲስ፣ ያገለገለ ወዘተ):",
        "category_prompt": "የእቃው ዘርፍ/ምድብ ይምረጡ (Choose Category):",
        "post_success": "መረጃዎ በተሳካ ሁኔታ ተመዝግቧል። በአድሚን ከታየ በኋላ በቻናላችን ይፖሰታል፣ እናመሰግናለን!",
        "verify_intro": (
            "🛡 <b>የሻጭ ማረጋገጫ ምዝገባ (Seller Verification)</b>\n\n"
            "የተረጋገጠ ሻጭ (Verified Seller) ሲሆኑ የእርስዎ እቃዎች በቻናሉ ላይ "
            "<b>'✅ የተረጋገጠ ሻጭ'</b> የሚል ምልክት ይኖራቸዋል።\n\n"
            "ሙሉ ስምዎን ያስገቡ:"
        ),
        "verify_phone": "የስልክ ቁጥርዎን ያስገቡ:",
        "verify_id_prompt": (
            "የመታወቂያ ፎቶ ይላኩ (ቀበሌ/መንጃ ፈቃድ/ፓስፖርት)።\n"
            "<i>(ማሳሰቢያ: መታወቂያዎ ለአድሚን ብቻ ነው የሚታየው፣ በቻናሉ ላይ አይፖሰትም)</i>\n\n"
            "ያለ መታወቂያ ለመቀጠል <b>Skip</b> የሚለውን ይጫኑ:"
        ),
        "verify_submitted": "✅ ማመልከቻዎ ለአድሚን ደርሷል! ከተረጋገጠ በኋላ ማሳወቂያ ይደርስዎታል።"
    },
    "en": {
        "welcome": (
            f"Welcome to <b>{BRAND_NAME}</b>!\n\n"
            "Easily search for items to buy, browse categories, or submit your own items for sale."
        ),
        "btn_search": "🔍 Search Items",
        "btn_browse": "📂 Browse Categories",
        "btn_post": "➕ Post an Item",
        "btn_my_listings": "📋 My Listings",
        "btn_verify": "🛡 Seller Verification",
        "btn_channels": "📢 Channel Links",
        "btn_lang_toggle": "🌐 አማርኛ",
        "search_prompt": (
            "🔍 <b>Enter item name, max price, city, or serial number:</b>\n\n"
            "<i>Examples:</i>\n"
            "• <code>iphone 20000 Gondar</code>\n"
            "• <code>sofa 15k Bahirdar</code>\n"
            "• <code>050 EL 015</code> (Exact serial)"
        ),
        "no_results": "😔 <b>No matching items found.</b>\n\nWould you like to be notified when a matching item is posted?",
        "notify_btn": "🔔 Notify Me on Match",
        "alert_saved": "✅ Alert saved! You will receive a message when a matching item is published.",
        "view_channel": "🔗 View on Channel",
        "browse_title": "📂 <b>Select a category:</b>",
        "my_listings_title": "📋 <b>Your Submitted Listings:</b>\n\n",
        "no_listings": "You haven't submitted any listings yet. Tap <b>➕ Post an Item</b> to start.",
        "channels_title": f"📢 <b>Official {BRAND_NAME} Channels:</b>\n\nJoin our dedicated category channels:\n\n",
        "photo_prompt": "Please send a clear photo of the item:",
        "name_prompt": "Enter the item name/title:",
        "price_prompt": "What is the price of the item?",
        "city_prompt": "Choose city:",
        "place_prompt": "Enter specific location / neighborhood (e.g. Arada, Bole):",
        "phone_prompt": "Enter contact phone number:",
        "condition_prompt": "What is the condition of the item? (New, Used, etc.):",
        "category_prompt": "Choose category:",
        "post_success": "Your listing has been submitted! It will appear on our channels after admin approval. Thank you!",
        "verify_intro": (
            "🛡 <b>Seller Verification Registration</b>\n\n"
            "Verified Sellers get a prominent <b>'✅ Verified Seller'</b> badge on all channel posts.\n\n"
            "Please enter your full legal name:"
        ),
        "verify_phone": "Please enter your phone number:",
        "verify_id_prompt": (
            "Please send a photo of your ID (National ID, Kebele ID, Passport, or Driver's License).\n"
            "<i>(Note: Your ID is stored securely for admins only and will NEVER be shared publicly)</i>\n\n"
            "To submit without ID, tap <b>Skip</b>:"
        ),
        "verify_submitted": "✅ Verification request submitted! Admins will review your application shortly."
    }
}

async def get_user_lang(user_id: int) -> str:
    try:
        async with AsyncSessionLocal() as session:
            pref = await session.get(UserPreference, user_id)
            if pref and pref.language in ("am", "en"):
                return pref.language
    except Exception:
        pass
    return "am"

async def set_user_lang(user_id: int, lang: str):
    try:
        async with AsyncSessionLocal() as session:
            pref = await session.get(UserPreference, user_id)
            if pref:
                pref.language = lang
            else:
                session.add(UserPreference(user_id=user_id, language=lang))
            await session.commit()
    except Exception as e:
        logger.error(f"Error setting user language: {e}")

def get_main_menu_keyboard(lang: str) -> ReplyKeyboardMarkup:
    t = MESSAGES.get(lang, MESSAGES["am"])
    kb = [
        [KeyboardButton(text=t["btn_search"]), KeyboardButton(text=t["btn_browse"])],
        [KeyboardButton(text=t["btn_post"]), KeyboardButton(text=t["btn_my_listings"])],
        [KeyboardButton(text=t["btn_verify"]), KeyboardButton(text=t["btn_channels"])],
        [KeyboardButton(text=t["btn_lang_toggle"])]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- FSM States ---
class ItemForm(StatesGroup):
    photo = State()
    name = State()
    price = State()
    city = State()
    place = State()
    phone = State()
    condition = State()
    category = State()

class SearchForm(StatesGroup):
    waiting_for_query = State()

class SellerVerifyForm(StatesGroup):
    name = State()
    phone = State()
    id_photo = State()

# --- Global Error Handler ---
@dp.error()
async def bot_error_handler(event: ErrorEvent):
    if isinstance(event.exception, TelegramRetryAfter):
        wait_seconds = event.exception.retry_after
        logger.warning(f"Aiogram FloodWait in bot handler: sleeping {wait_seconds}s")
        await asyncio.sleep(wait_seconds)
        return True
    logger.error(f"Bot update processing error: {event.exception}", exc_info=event.exception)

# --- Start & Navigation Handlers ---
@dp.message(CommandStart())
async def command_start(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    await message.answer(
        t["welcome"],
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(lang)
    )

@dp.message(Command("menu"))
async def command_menu(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    await message.answer(
        t["welcome"],
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(lang)
    )

@dp.message(Command("search"))
@dp.message(F.text.in_(["🔍 እቃ ፈልግ", "🔍 Search Items"]))
async def trigger_search(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    await message.answer(t["search_prompt"], parse_mode="HTML")
    await state.set_state(SearchForm.waiting_for_query)

@dp.message(F.text.in_(["🌐 English", "🌐 አማርኛ"]))
async def toggle_language(message: Message, state: FSMContext):
    current_lang = await get_user_lang(message.from_user.id)
    new_lang = "en" if current_lang == "am" else "am"
    await set_user_lang(message.from_user.id, new_lang)
    
    t = MESSAGES[new_lang]
    ack = "Language set to English." if new_lang == "en" else "ቋንቋ ወደ አማርኛ ተቀይሯል።"
    await message.answer(
        f"{ack}\n\n{t['welcome']}",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(new_lang)
    )

@dp.message(Command("browse"))
@dp.message(F.text.in_(["📂 በዘርፍ መርጥ", "📂 Browse Categories"]))
async def browse_categories(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]

    buttons = [
        [
            InlineKeyboardButton(text="💄 Cosmetics (ኮስሞቲክስ)", callback_data="cat:Cosmetics"),
            InlineKeyboardButton(text="📱 Electronics (ኤሌክትሮኒክስ)", callback_data="cat:Electronics")
        ],
        [
            InlineKeyboardButton(text="🚗 Vehicles (መኪና)", callback_data="cat:Vehicles"),
            InlineKeyboardButton(text="🛋 Furniture (ፈርኒቸር)", callback_data="cat:Furniture")
        ],
        [
            InlineKeyboardButton(text="👕 Clothing (ልብስ እና ጫማ)", callback_data="cat:Clothing"),
            InlineKeyboardButton(text="🏠 House/Rent (ቤት)", callback_data="cat:House/Rent")
        ],
        [
            InlineKeyboardButton(text="📦 Others (ሌሎች)", callback_data="cat:Others")
        ]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(t["browse_title"], parse_mode="HTML", reply_markup=markup)

@dp.message(F.text.in_(["📢 ቻናሎች", "📢 Channel Links"]))
async def show_channel_links(message: Message):
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    
    clean_main = CHANNEL_ID.replace("@", "")
    text_content = t["channels_title"]
    text_content += f"🌟 <b>ዋና ቻናል (Main Hub):</b> https://t.me/{clean_main}\n\n"
    
    cat_icons = {
        "Cosmetics": "💄",
        "Electronics": "📱",
        "Vehicles": "🚗",
        "Furniture": "🛋",
        "Clothing": "👕",
        "House/Rent": "🏠",
        "Others": "📦"
    }
    for cat_name, channel_ref in CATEGORY_CHANNELS.items():
        if cat_name == "Others":
            continue
        icon = cat_icons.get(cat_name, "🛍")
        clean_handle = channel_ref.replace("@", "")
        text_content += f"{icon} <b>{cat_name}:</b> https://t.me/{clean_handle}\n"

    await message.answer(text_content, parse_mode="HTML", disable_web_page_preview=True)

# --- Seller Verification Flow ---
@dp.message(Command("verify"))
@dp.message(F.text.in_(["🛡 የሻጭ ማረጋገጫ", "🛡 Seller Verification"]))
async def start_seller_verification(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]

    # Check if already verified
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(
            select(Seller).where(Seller.telegram_user_id == message.from_user.id)
        )
        if existing:
            if existing.status == "approved":
                ack = "✅ የእርስዎ መለያ ቀድሞውኑ የተረጋገጠ ነው (Verified Seller)!" if lang == "am" else "✅ Your seller account is already verified!"
                await message.answer(ack)
                return
            elif existing.status == "pending":
                ack = "⏳ ማመልከቻዎ በአድሚን በግምገማ ላይ ነው፤ እባክዎ በትዕግስት ይጠብቁ።" if lang == "am" else "⏳ Your verification application is pending admin review."
                await message.answer(ack)
                return

    await message.answer(t["verify_intro"], parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await state.set_state(SellerVerifyForm.name)

@dp.message(SellerVerifyForm.name)
async def process_seller_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    await state.update_data(seller_name=name)
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    await message.answer(t["verify_phone"])
    await state.set_state(SellerVerifyForm.phone)

@dp.message(SellerVerifyForm.phone)
async def process_seller_phone(message: Message, state: FSMContext):
    phone = (message.text or "").strip()
    await state.update_data(seller_phone=phone)
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]

    skip_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Skip")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(t["verify_id_prompt"], parse_mode="HTML", reply_markup=skip_kb)
    await state.set_state(SellerVerifyForm.id_photo)

@dp.message(SellerVerifyForm.id_photo, F.photo)
async def process_seller_id_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    photo = message.photo[-1]
    
    # Save securely in private directory
    os.makedirs(os.path.join("secure_uploads", "ids"), exist_ok=True)
    filename = f"id_{user_id}_{int(datetime.utcnow().timestamp())}.jpg"
    filepath = os.path.join("secure_uploads", "ids", filename)
    await bot.download(photo.file_id, destination=filepath)

    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        seller = await session.scalar(select(Seller).where(Seller.telegram_user_id == user_id))
        if seller:
            seller.name = data["seller_name"]
            seller.phone = data["seller_phone"]
            seller.username = message.from_user.username
            seller.id_photo_path = filepath
            seller.status = "pending"
        else:
            session.add(Seller(
                telegram_user_id=user_id,
                name=data["seller_name"],
                phone=data["seller_phone"],
                username=message.from_user.username,
                id_photo_path=filepath,
                status="pending"
            ))
        await session.commit()

    await state.clear()
    lang = await get_user_lang(user_id)
    t = MESSAGES[lang]
    await message.answer(t["verify_submitted"], reply_markup=get_main_menu_keyboard(lang))

@dp.message(SellerVerifyForm.id_photo)
async def process_seller_id_skip(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        seller = await session.scalar(select(Seller).where(Seller.telegram_user_id == user_id))
        if seller:
            seller.name = data.get("seller_name", "Unknown")
            seller.phone = data.get("seller_phone", "N/A")
            seller.username = message.from_user.username
            seller.status = "pending"
        else:
            session.add(Seller(
                telegram_user_id=user_id,
                name=data.get("seller_name", "Unknown"),
                phone=data.get("seller_phone", "N/A"),
                username=message.from_user.username,
                id_photo_path=None,
                status="pending"
            ))
        await session.commit()

    await state.clear()
    lang = await get_user_lang(user_id)
    t = MESSAGES[lang]
    await message.answer(t["verify_submitted"], reply_markup=get_main_menu_keyboard(lang))

# --- My Listings & Mark As Sold Flow ---
@dp.message(F.text.in_(["📋 የእኔ እቃዎች", "📋 My Listings"]))
async def show_my_listings(message: Message):
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    user_id = message.from_user.id
    username = (message.from_user.username or "").strip()

    # Match by telegram_user_id OR username
    async with AsyncSessionLocal() as session:
        conditions = [Item.telegram_user_id == user_id]
        if username:
            conditions.append(Item.username.ilike(username))
        
        result = await session.execute(
            select(Item).where(or_(*conditions)).order_by(Item.id.desc())
        )
        my_items = result.scalars().all()

    if not my_items:
        await message.answer(t["no_listings"], parse_mode="HTML")
        return

    await message.answer(t["my_listings_title"], parse_mode="HTML")

    status_labels = {
        ItemStatus.POSTED: ("🟢 ይፋ ሆኗል (Posted)", True),
        ItemStatus.PARTIALLY_POSTED: ("🟡 በከፊል (Partially Posted)", True),
        ItemStatus.PENDING: ("⏳ በግምገማ ላይ (Pending)", False),
        ItemStatus.SOLD: ("🔴 ተሽጧል (Sold)", False),
        ItemStatus.SCHEDULED: ("🟣 ቀጠሮ የተያዘለት (Scheduled)", False)
    }

    for item in my_items:
        serial = get_item_serial(item)
        st_text, can_mark_sold = status_labels.get(item.status, (str(item.status), False))

        card_text = (
            f"🏷 <b>{html.escape(item.name)}</b>\n"
            f"🔖 <b>መለያ ቁጥር:</b> <code>{serial}</code>\n"
            f"💰 <b>ዋጋ:</b> {html.escape(item.price)} | {st_text}\n"
        )

        buttons = []
        # If item is live, allow seller to mark it as sold
        if can_mark_sold:
            buttons.append([InlineKeyboardButton(text="🔴 ተሽጧል (Mark as SOLD)", callback_data=f"mysold:{item.id}")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
        await message.answer(card_text, parse_mode="HTML", reply_markup=kb)

@dp.callback_query(F.data.startswith("mysold:"))
async def on_seller_mark_sold(callback: CallbackQuery):
    """Allows sellers to mark their OWN items as SOLD directly from the bot."""
    item_id_str = callback.data.split("mysold:", 1)[1]
    try:
        item_id = int(item_id_str)
    except ValueError:
        return

    user_id = callback.from_user.id
    username = (callback.from_user.username or "").lower()

    async with AsyncSessionLocal() as session:
        item = await session.get(Item, item_id)
        if not item:
            await callback.answer("እቃው አልተገኘም / Item not found.", show_alert=True)
            return

        # Verification: must be owner by telegram_user_id or username
        is_owner = (item.telegram_user_id == user_id) or (item.username and item.username.lower() == username)
        if not is_owner:
            await callback.answer("ይህንን እቃ ማስተካከል የሚችሉት ባለቤቱ ብቻ ናቸው! / Only the owner can mark this as sold.", show_alert=True)
            return

        if item.status == ItemStatus.SOLD:
            await callback.answer("እቃው አስቀድሞ ተሽጧል / Item already marked as sold.", show_alert=True)
            return

        # Edit caption on live Telegram channels
        sold_text = get_sold_caption(item)

        if item.channel_chat_id and item.channel_message_id:
            try:
                await bot.edit_message_caption(
                    chat_id=item.channel_chat_id,
                    message_id=item.channel_message_id,
                    caption=sold_text,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Could not edit main channel post for sold item {item.id}: {e}")

        if item.category_chat_id and item.category_message_id and item.category_chat_id != item.channel_chat_id:
            try:
                await bot.edit_message_caption(
                    chat_id=item.category_chat_id,
                    message_id=item.category_message_id,
                    caption=sold_text,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Could not edit category channel post for sold item {item.id}: {e}")

        item.status = ItemStatus.SOLD
        item.post_error = None
        await session.commit()

    await callback.answer("✅ እቃው በተሳካ ሁኔታ ተሽጧል ተብሎ ተዘምኗል! / Marked as SOLD on channel!", show_alert=True)
    await callback.message.edit_text(f"❌ <b>ተሽጧል (SOLD):</b> {html.escape(item.name)} ({get_item_serial(item)})", parse_mode="HTML")

# --- Pre-Expiry Availability Callback Handlers ---
@dp.callback_query(F.data.startswith("avail:"))
async def on_availability_response(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    _, action, item_id_str = parts
    try:
        item_id = int(item_id_str)
    except ValueError:
        return

    async with AsyncSessionLocal() as session:
        item = await session.get(Item, item_id)
        if not item:
            await callback.answer("እቃው አልተገኘም / Item not found.", show_alert=True)
            return

        if action == "keep":
            # Extend listing by 7 days
            item.created_at = datetime.utcnow()
            item.expiry_warning_sent = 0
            await session.commit()
            await callback.answer("✅ የእቃው ጊዜ ለተጨማሪ 7 ቀናት ተራዝሟል! / Listing extended for 7 days!", show_alert=True)
            await callback.message.edit_text(
                f"✅ <b>የእቃው ቆይታ ተራዝሟል:</b> {html.escape(item.name)}\nእቃው በቻናሉ ላይ ንቁ ሆኖ ይቀጥላል።",
                parse_mode="HTML"
            )
        elif action == "sold":
            # Mark as SOLD
            sold_text = get_sold_caption(item)
            if item.channel_chat_id and item.channel_message_id:
                try:
                    await bot.edit_message_caption(
                        chat_id=item.channel_chat_id,
                        message_id=item.channel_message_id,
                        caption=sold_text,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

            item.status = ItemStatus.SOLD
            await session.commit()
            await callback.answer("✅ እቃው ተሽጧል ተብሎ ተዘምኗል! / Marked as SOLD!", show_alert=True)
            await callback.message.edit_text(
                f"❌ <b>ተሽጧል (SOLD):</b> {html.escape(item.name)}",
                parse_mode="HTML"
            )

# --- Reporting Flow ---
@dp.callback_query(F.data.startswith("report:"))
async def on_report_click(callback: CallbackQuery):
    item_id = callback.data.split("report:", 1)[1]
    buttons = [
        [InlineKeyboardButton(text="⚠️ አሳሳች ዋጋ / False Price", callback_data=f"repreas:false_price:{item_id}")],
        [InlineKeyboardButton(text="❌ አስቀድሞ ተሽጧል / Already Sold", callback_data=f"repreas:already_sold:{item_id}")],
        [InlineKeyboardButton(text="🚫 ማጭበርበር / Scam", callback_data=f"repreas:scam:{item_id}")],
        [InlineKeyboardButton(text="📝 ሌላ ምክንያት / Other Issue", callback_data=f"repreas:other:{item_id}")]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer("🚩 <b>ይህንን እቃ ለምን ሪፖርት ማድረግ ፈለጉ? (Report Reason):</b>", parse_mode="HTML", reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data.startswith("repreas:"))
async def on_report_reason_chosen(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    _, reason_code, item_id_str = parts
    try:
        item_id = int(item_id_str)
    except ValueError:
        return

    reason_labels = {
        "false_price": "False Price / አሳሳች ዋጋ",
        "already_sold": "Already Sold / አስቀድሞ ተሽጧል",
        "scam": "Scam / ማጭበርበር",
        "other": "Other / ሌላ"
    }
    reason_text = reason_labels.get(reason_code, reason_code)

    try:
        async with AsyncSessionLocal() as session:
            new_report = Report(
                item_id=item_id,
                reporter_user_id=callback.from_user.id,
                reason=reason_text,
                status="pending"
            )
            session.add(new_report)
            await session.commit()

        await callback.answer("✅ ሪፖርትዎ ለአድሚን ደርሷል። እናመሰግናለን! / Report submitted.", show_alert=True)
        await callback.message.delete()
    except Exception as e:
        logger.error(f"Error saving report: {e}")
        await callback.answer("Could not submit report.", show_alert=True)

# --- Search Execution & Paged Card Presentation ---
def build_card_caption(item: Item, lang: str, page_idx: int, total_pages: int) -> str:
    serial = get_item_serial(item)

    verified_badge = "✅ <b>የተረጋገጠ ሻጭ (Verified Seller)</b>\n" if item.is_verified else ""
    lines = [
        verified_badge + f"🏷 <b>{html.escape(item.name)}</b>",
        f"🔖 <b>መለያ ቁጥር:</b> <code>{serial}</code>",
        "━━━━━━━━━━━━━━━━━━━",
        f"ℹ️ <b>ሁኔታ:</b> {html.escape(item.condition or 'ያገለገለ')}",
        f"📍 <b>ቦታ:</b> {html.escape(item.location or 'Gondar')}",
        f"💰 <b>ዋጋ:</b> <code>{html.escape(item.price or 'N/A')}</code> ብር"
    ]
    if item.username:
        clean_user = item.username.replace("@", "")
        lines.append(f"👤 <b>ሻጭ inbox:</b> @{html.escape(clean_user)}")
    if item.phone:
        lines.append(f"📞 <b>ስልክ ቁጥር:</b> {html.escape(item.phone)}")

    lines.append("━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📄 <i>{page_idx + 1} / {total_pages}</i>")
    return "\n".join(lines)

def build_card_markup(item: Item, search_id: str, page_idx: int, total_pages: int, lang: str) -> InlineKeyboardMarkup:
    t = MESSAGES[lang]
    rows = []

    # Row 1: Direct link to channel post if published
    channel_link = None
    target_chat = item.channel_chat_id or CHANNEL_ID
    if item.channel_message_id and target_chat:
        clean_handle = target_chat.replace("@", "")
        channel_link = f"https://t.me/{clean_handle}/{item.channel_message_id}"

    if channel_link:
        rows.append([InlineKeyboardButton(text=t["view_channel"], url=channel_link)])

    # Row 2: Pagination controls
    nav_buttons = []
    if page_idx > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ ወደ ኋላ", callback_data=f"page:{search_id}:{page_idx-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page_idx+1}/{total_pages}", callback_data="noop"))
    if page_idx < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="ወደ ፊት ➡️", callback_data=f"page:{search_id}:{page_idx+1}"))
    rows.append(nav_buttons)

    # Row 3: Action Buttons (Notify Me & Report)
    action_buttons = [
        InlineKeyboardButton(text=t["notify_btn"], callback_data=f"alert:{search_id}"),
        InlineKeyboardButton(text="🚩 ሪፖርት (Report)", callback_data=f"report:{item.id}")
    ]
    rows.append(action_buttons)

    return InlineKeyboardMarkup(inline_keyboard=rows)

async def send_result_card(target_message: Message, item: Item, search_id: str, page_idx: int, total_pages: int, lang: str):
    caption = build_card_caption(item, lang, page_idx, total_pages)
    markup = build_card_markup(item, search_id, page_idx, total_pages, lang)

    photo_file = None
    if item.photo_file_id:
        p_id = item.photo_file_id.split(",")[0].strip()
        if p_id.startswith("local:"):
            fn = p_id.replace("local:", "")
            fp = os.path.join("uploads", fn)
            if os.path.exists(fp):
                photo_file = FSInputFile(fp)
        else:
            photo_file = p_id

    try:
        if photo_file:
            await target_message.answer_photo(photo_file, caption=caption, parse_mode="HTML", reply_markup=markup)
        else:
            await target_message.answer(caption, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        logger.warning(f"Could not send photo for item {item.id}: {e}. Sending text fallback.")
        await target_message.answer(caption, parse_mode="HTML", reply_markup=markup)

async def handle_search_query(message: Message, query_text: str, category_filter: str | None = None):
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]

    results = await execute_search(query_text, category_filter=category_filter, limit=40)

    if not results:
        search_id = uuid.uuid4().hex[:10]
        search_cache[search_id] = {
            "query": query_text,
            "category": category_filter,
            "item_ids": []
        }
        prune_search_cache()

        no_res_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t["notify_btn"], callback_data=f"alert:{search_id}")]
        ])
        await message.answer(t["no_results"], parse_mode="HTML", reply_markup=no_res_markup)
        return

    search_id = uuid.uuid4().hex[:10]
    search_cache[search_id] = {
        "query": query_text,
        "category": category_filter,
        "item_ids": [it.id for it in results]
    }
    prune_search_cache()

    total_pages = len(results)
    await send_result_card(message, results[0], search_id, 0, total_pages, lang)

@dp.message(SearchForm.waiting_for_query)
async def process_search_input(message: Message, state: FSMContext):
    await state.clear()
    query = message.text or ""
    await handle_search_query(message, query)

# --- Category Browser Callback ---
@dp.callback_query(F.data.startswith("cat:"))
async def on_category_selected(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    category = callback.data.split("cat:", 1)[1]
    await handle_search_query(callback.message, query_text="", category_filter=category)

# --- Pagination Callback ---
@dp.callback_query(F.data.startswith("page:"))
async def on_page_navigation(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    _, search_id, page_str = parts
    try:
        page_idx = int(page_str)
    except ValueError:
        return

    cache_entry = search_cache.get(search_id)
    if not cache_entry:
        await callback.message.answer("ይህ ፍለጋ ጊዜው አልፎበታል፤ እባክዎ እንደገና ይፈልጉ። / Search expired.")
        return

    item_ids = cache_entry.get("item_ids", [])
    if not item_ids or page_idx < 0 or page_idx >= len(item_ids):
        return

    target_item_id = item_ids[page_idx]
    async with AsyncSessionLocal() as session:
        item = await session.get(Item, target_item_id)

    if not item:
        return

    lang = await get_user_lang(callback.from_user.id)
    total_pages = len(item_ids)
    await send_result_card(callback.message, item, search_id, page_idx, total_pages, lang)

# --- Notify Me Alert Callback ---
@dp.callback_query(F.data.startswith("alert:"))
async def on_save_alert(callback: CallbackQuery):
    search_id = callback.data.split("alert:", 1)[1]
    cache_entry = search_cache.get(search_id, {})
    query_text = cache_entry.get("query") or "General Search"
    category = cache_entry.get("category")
    parsed = parse_search_query(query_text)

    lang = await get_user_lang(callback.from_user.id)
    t = MESSAGES[lang]

    try:
        async with AsyncSessionLocal() as session:
            new_alert = SearchAlert(
                user_id=callback.from_user.id,
                query=query_text,
                normalized_query=" ".join(parsed.keywords),
                category=category or parsed.category,
                max_price=parsed.max_price,
                is_active=1
            )
            session.add(new_alert)
            await session.commit()

        await callback.answer(t["alert_saved"], show_alert=True)
    except Exception as e:
        logger.error(f"Error saving search alert: {e}")
        await callback.answer("Could not save alert.", show_alert=True)

@dp.callback_query(F.data == "noop")
async def on_noop(callback: CallbackQuery):
    await callback.answer()

# --- Seller Submission Flow (Preserved and Refined) ---
@dp.message(F.text.in_(["➕ እቃ ለመሸጥ", "➕ Post an Item"]))
async def start_post_item(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    await message.answer(t["photo_prompt"], reply_markup=ReplyKeyboardRemove())
    await state.set_state(ItemForm.photo)

@dp.message(ItemForm.photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    await message.answer(t["name_prompt"])
    await state.set_state(ItemForm.name)

@dp.message(ItemForm.photo)
async def process_photo_invalid(message: Message):
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    await message.answer(t["photo_prompt"])

@dp.message(ItemForm.name)
async def process_name(message: Message, state: FSMContext):
    clean_name = re.sub(r'(?i)\b(?:https?://|www\.|t\.me/)\S+|@\S+', '', message.text or "").strip()
    clean_name = re.sub(r'[\-\s]+$', '', clean_name)
    await state.update_data(name=clean_name)
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    await message.answer(t["price_prompt"])
    await state.set_state(ItemForm.price)

@dp.message(ItemForm.price)
async def process_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    kb = [
        [KeyboardButton(text="Gondar"), KeyboardButton(text="Bahirdar")],
        [KeyboardButton(text="Addis Ababa")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    await message.answer(t["city_prompt"], reply_markup=keyboard)
    await state.set_state(ItemForm.city)

@dp.message(ItemForm.city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    await message.answer(t["place_prompt"], reply_markup=ReplyKeyboardRemove())
    await state.set_state(ItemForm.place)

@dp.message(ItemForm.place)
async def process_place(message: Message, state: FSMContext):
    data = await state.get_data()
    city = data.get('city', 'Gondar')
    place = message.text or ""
    full_location = f"({city}) {place}"
    await state.update_data(location=full_location)
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    await message.answer(t["phone_prompt"])
    await state.set_state(ItemForm.phone)

@dp.message(ItemForm.phone)
async def process_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    await message.answer(t["condition_prompt"])
    await state.set_state(ItemForm.condition)

@dp.message(ItemForm.condition)
async def process_condition(message: Message, state: FSMContext):
    await state.update_data(condition=message.text)
    cat_kb = [
        [KeyboardButton(text="Cosmetics (ኮስሞቲክስ)"), KeyboardButton(text="Electronics (ኤሌክትሮኒክስ)")],
        [KeyboardButton(text="Furniture (ፈርኒቸር)"), KeyboardButton(text="Clothing (ልብስ እና ጫማ)")],
        [KeyboardButton(text="House/Rent (ቤት)"), KeyboardButton(text="Vehicles (መኪና)")],
        [KeyboardButton(text="Others (ሌሎች)")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=cat_kb, resize_keyboard=True, one_time_keyboard=True)
    lang = await get_user_lang(message.from_user.id)
    t = MESSAGES[lang]
    await message.answer(t["category_prompt"], reply_markup=keyboard)
    await state.set_state(ItemForm.category)

@dp.message(ItemForm.category)
async def process_category(message: Message, state: FSMContext):
    raw_cat = message.text or ""
    cat_map = {
        "Cosmetics": "Cosmetics",
        "Electronics": "Electronics",
        "Furniture": "Furniture",
        "Clothing": "Clothing",
        "House/Rent": "House/Rent",
        "Vehicles": "Vehicles"
    }
    canonical_cat = "Others"
    for k, v in cat_map.items():
        if k.lower() in raw_cat.lower():
            canonical_cat = v
            break

    user_id = message.from_user.id
    username = message.from_user.username or ""
    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        # Check if seller is approved to grant verified status
        approved_seller = await session.scalar(
            select(Seller).where(
                Seller.telegram_user_id == user_id,
                Seller.status == "approved"
            )
        )
        is_verified = 1 if approved_seller else 0

        new_item = Item(
            photo_file_id=data['photo_id'],
            name=data['name'],
            price=data['price'],
            location=data['location'],
            phone=data['phone'],
            condition=data['condition'],
            username=username,
            telegram_user_id=user_id,
            category=canonical_cat,
            is_verified=is_verified,
            status=ItemStatus.PENDING
        )
        session.add(new_item)
        await session.commit()

    await state.clear()
    lang = await get_user_lang(user_id)
    t = MESSAGES[lang]
    await message.answer(
        t["post_success"],
        reply_markup=get_main_menu_keyboard(lang)
    )

# --- Fallback Free-Text Search Handler ---
@dp.message(F.text)
async def on_general_text_search(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return
    query = (message.text or "").strip()
    if len(query) >= 2:
        await handle_search_query(message, query)
