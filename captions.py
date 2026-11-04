import html
import re
from database import Item
from config import (
    BRAND_NAME,
    BRAND_HASHTAG,
    CHANNEL_ID,
    CATEGORY_TAGS,
    ITEM_SHORTHANDS
)

def get_item_serial(item: Item) -> str:
    """Computes the 050 EL 015 / 050 CO 015 formatted ID."""
    code = ITEM_SHORTHANDS.get(item.category, "OT")
    global_id = str(item.id).zfill(3)
    cat_seq = str(item.category_id_seq or 0).zfill(3)
    return f"{global_id} {code} {cat_seq}"

def get_caption(item: Item) -> str:
    """
    Builds the standardized Bete Dires channel caption.
    Verification line is conditional: only displays 'Verified Seller' and 'Verified Item'
    if item.is_verified is True.
    """
    tag = CATEGORY_TAGS.get(item.category, "#Market")
    
    # Serial ID
    serial = html.escape(get_item_serial(item))
    safe_name = html.escape(item.name)
    safe_condition = html.escape(item.condition or "")
    safe_location = html.escape(item.location or "")
    
    caption = f"🏷 <b>{safe_name}</b>\n"
    caption += f"🔖 <b>መለያ ቁጥር: </b> <code>{serial}</code>\n"
    caption += f"━━━━━━━━━━━━━━━━━━━\n"
    caption += f"ℹ️ <b>የእቃው ሁኔታ: </b> {safe_condition}\n"
    caption += f"📍 <b>ቦታ: </b> {safe_location}\n"
    
    price_display = html.escape(str(item.price or ""))
    if "~~" in price_display:
        price_display = re.sub(r'~~(.*?)~~', r'<s>\1</s>', price_display)
        caption += f"💰 <b>ዋጋ: </b> {price_display} <b>ብር </b>\n"
    else:
        caption += f"💰 <b>ዋጋ: </b> <code>{price_display}</code> <b>ብር </b>\n"
        
    if item.username and item.username.strip():
        safe_username = html.escape(item.username.replace('@', ''))
        caption += f"👤 <b>ሻጭ inbox:</b> @{safe_username}\n"
    safe_phone = html.escape(item.phone or "")
    caption += f"📞 <b>ስልክ ቁጥር:</b> {safe_phone}\n"
    caption += f"━━━━━━━━━━━━━━━━━━━\n"
    
    main_handle = (item.channel_chat_id or CHANNEL_ID).replace('@', '')
    if item.is_verified:
        caption += f"✅ <b>የተረጋገጠ ሻጭ (Verified Seller)</b>\n"
        caption += f"✅ <i>የተረጋገጠ እቃ በ @{main_handle}</i>\n\n"
    else:
        caption += f"🛍 <i>በ @{main_handle} የቀረበ</i>\n\n"

    caption += f"{tag} {BRAND_HASHTAG}"
    return caption

def get_sold_caption(item: Item) -> str:
    """Builds caption when an item is marked as SOLD."""
    serial = get_item_serial(item)
    main_handle = (item.channel_chat_id or CHANNEL_ID).replace('@', '')
    ver_tag = f"✅ <i>Verified at @{main_handle}</i>" if item.is_verified else f"🛍 <i>@{main_handle}</i>"
    return (
        f"❌ <b>ተሽጧል (SOLD)</b>\n\n"
        f"🏷 <b>{item.name}</b>\n"
        f"🔖 <b>መለያ ቁጥር:</b> <code>{serial}</code>\n"
        f"📍 <b>ቦታ:</b> {item.location}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{ver_tag}"
    )
