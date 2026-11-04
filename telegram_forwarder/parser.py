import re
import html
import hashlib
import os

# Emoji regex for leading emoji cleanup
EMOJI_PATTERN = re.compile(
    r'^[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF\U0001F300-\U0001FAFF'
    r'\u00A9\u00AE\u203C\u2049\u20E3\u2122\u2139\u231A\u231B\u23E9-\u23F3\u23F8-\u23FA'
    r'\u24C2\u25AA\u25AB\u25B6\u25C0\u25FB-\u25FE\u2600-\u2604\u260E\u2611\u2614\u2615'
    r'\u2618\u261D\u2620\u2622\u2623\u2626\u262A\u262E\u262F\u2638-\u263A\u2640\u2642'
    r'\u2648-\u2653\u265F\u2660\u2663\u2665\u2666\u2668\u267B\u267E\u267F\u2692-\u2697'
    r'\u2699\u269B\u269C\u26A0\u26A1\u26AA\u26AB\u26B0\u26B1\u26BD\u26BE\u26C4\u26C5'
    r'\u26CE\u26CF\u26D1\u26D3\u26D4\u26E9\u26EA\u26F0-\u26F5\u26F7-\u26FA\u26FD\u2702'
    r'\u2705\u2708-\u270D\u270F\u2712\u2714\u2716\u271D\u2721\u2728\u2733\u2734\u2744'
    r'\u2747\u274C\u274E\u2753-\u2755\u2757\u2763\u2764\u2795-\u2797\u27A1\u27B0\u27BF'
    r'\u2934\u2935\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u3030\u303D\u3297\u3299🟡🟢🔴🔵🟠🟣⚫⚪🟤]+\s*'
)

# Category detection keywords (Amharic & English)
CATEGORY_KEYWORDS = {
    "Cosmetics": [
        "ሽቶ", "ሎሽን", "ክሬም", "ሜካፕ", "ሳሙና", "ዘይት", "ኮስሞቲክስ", "ውበት", "ፀጉር",
        "perfume", "lotion", "cream", "makeup", "soap", "cosmetics", "beauty", "hair"
    ],
    "Electronics": [
        "ስልክ", "ላፕቶፕ", "ኮምፒውተር", "ቴሌቪዥን", "ቲቪ", "አይፎን", "ሳምሰንግ", "ስማርት",
        "ፍሪጅ", "ማጠቢያ", "ስፒከር", "ካሜራ", "ቻርጀር", "ፕሮጀክተር", "ፕሌይስቴሽን", "ipad",
        "phone", "laptop", "computer", "tv", "television", "iphone", "samsung", "camera",
        "charger", "projector", "speaker", "playstation", "ps4", "ps5", "fridge", "printer"
    ],
    "Vehicles": [
        "መኪና", "ባጃጅ", "ሞተር", "ቪትዝ", "ቶዮታ", "ያሪስ", "ኮሮላ", "አውቶሞቢል", "ሳይክል",
        "car", "vehicle", "automobile", "motorcycle", "motor", "bajaj", "vitz", "toyota", "yaris", "corolla"
    ],
    "Furniture": [
        "ሶፋ", "አልጋ", "ቁምሳጥን", "ቡፌ", "ጠረጴዛ", "ወንበር", "መደርደሪያ", "ፍራሽ", "መጋረጃ",
        "furniture", "sofa", "bed", "chair", "table", "closet", "wardrobe", "mattress", "curtain"
    ],
    "Clothing": [
        "ልብስ", "ጫማ", "ጃኬት", "ሱሪ", "ቀሚስ", "ሸሚዝ", "ኮት", "ቦርሳ", "ካፖርት",
        "clothing", "clothes", "shoe", "shoes", "jacket", "pants", "dress", "shirt", "coat", "bag"
    ],
    "House/Rent": [
        "ቤት", "ኪራይ", "ቪላ", "ኮንዶሚኒየም", "አፓርታማ", "ግቢ", "መሬት",
        "house", "rent", "villa", "condominium", "apartment", "compound", "land"
    ]
}

def strip_emojis_from_line(line: str) -> str:
    """Strips leading emojis and symbols from a line."""
    return EMOJI_PATTERN.sub('', line)

def normalize_text(text: str) -> str:
    """
    Normalizes text for deduplication and search:
    collapses whitespace, strips emojis/punctuation, lowers ASCII characters.
    """
    if not text:
        return ""
    # Strip emojis
    cleaned = EMOJI_PATTERN.sub(' ', text)
    # Lowercase ASCII characters
    cleaned = cleaned.lower()
    # Replace newlines and punctuation with space
    cleaned = re.sub(r'[\r\n\t\-_:;,\.!\?\(\)\[\]/\\\'"`~#*]', ' ', cleaned)
    # Collapse multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def detect_category(text: str, item_name: str = "") -> str:
    """
    Infers category from the item name and message text.
    Returns one of: Cosmetics, Electronics, Vehicles, Furniture, Clothing, House/Rent, Others.
    """
    target = f"{item_name} {text}".lower()
    
    # Priority check: check each category keywords
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            # Word boundary or simple substring for Amharic
            pattern = re.compile(rf'(?:\b|^|\s){re.escape(kw)}(?:\b|$|\s)', re.IGNORECASE)
            if pattern.search(target) or kw in target:
                return cat
                
    return "Others"

def parse_source_text(text: str) -> dict:
    """
    Parses the source Telegram message and extracts the required fields.
    Handles emojis and symbols that may appear before keywords on each line.
    """
    data = {
        "item": "",
        "price": "",
        "location": "",
        "phone": "",
        "inbox": "",
        "condition": "ያገለገለ"
    }

    if not text:
        return data

    cleaned_lines = [strip_emojis_from_line(line) for line in text.splitlines()]
    cleaned_text = "\n".join(cleaned_lines)

    # 1. Extract Item Name
    item_match = re.search(r"የሚሸጠው እቃ\s*:-\s*(.*?)(?=\n|$)", cleaned_text)
    if item_match:
        raw_item = item_match.group(1).strip()
        clean_item = re.sub(r'(?i)\b(?:https?://|www\.|t\.me/)\S+|@\S+', '', raw_item).strip()
        clean_item = re.sub(r'[\-\s]+$', '', clean_item)
        clean_item = re.sub(r'^[<\[\(]+|[>\]\)]+$', '', clean_item).strip()
        data["item"] = clean_item

    # 2. Extract Price and Location
    price_loc_full_match = re.search(r"ዋጋ[^\n]*?[:\-]+\s*([^\n]+)", cleaned_text)
    if price_loc_full_match:
        full_val = price_loc_full_match.group(1).strip()
        
        # Extract location from brackets if they exist
        loc_match = re.search(r"\(([^)]+)\)", full_val)
        if loc_match:
            data["location"] = loc_match.group(1).strip()
            price_str = full_val[:loc_match.start()].strip()
        else:
            price_str = full_val
            
        # Convert "12 ሺ" or "12 ሺህ" to "12,000"
        price_str = re.sub(r'(\d+(?:\.\d+)?)\s*ሺህ?', lambda m: f"{int(float(m.group(1)) * 1000):,}", price_str)
        data["price"] = price_str

    # 3. Extract Phone
    phone_match = re.search(r"የባለቤቱ ቁጥር\s*:-\s*(\+?\d[\d\s\-]*)", cleaned_text)
    if phone_match:
        data["phone"] = phone_match.group(1).strip()

    # 4. Extract Inbox
    inbox_match = re.search(r"የባለቤቱ Inbox\s*:-\s*(@\S+)", cleaned_text)
    if inbox_match:
        data["inbox"] = inbox_match.group(1).strip()

    return data

def evaluate_confidence(parsed_data: dict) -> tuple[bool, str]:
    """
    Evaluates parsing confidence.
    High confidence requires: valid item title, valid price, and valid phone number.
    Returns (is_high_confidence: bool, reason: str).
    """
    item = parsed_data.get("item", "").strip()
    price = parsed_data.get("price", "").strip()
    phone = parsed_data.get("phone", "").strip()

    if not item or len(item) < 2:
        return False, "missing_item"

    # Price must have at least one digit
    if not price or not re.search(r'\d', price) or price.lower() in ("n/a", "none", "-"):
        return False, "missing_or_invalid_price"

    # Phone must have at least 9 digits
    phone_digits = re.sub(r'\D', '', phone)
    if not phone or len(phone_digits) < 9:
        return False, "missing_or_invalid_phone"

    return True, "high_confidence"

def compute_content_hash(text: str, image_bytes: bytes | None = None) -> str:
    """
    Computes a deduplication SHA-256 hash combining normalized text and image content.
    """
    norm_text = normalize_text(text)
    hasher = hashlib.sha256(norm_text.encode("utf-8"))
    if image_bytes:
        img_digest = hashlib.sha256(image_bytes).hexdigest()
        hasher.update(img_digest.encode("utf-8"))
    return hasher.hexdigest()

def format_target_text(
    data: dict,
    serial: str,
    channel_handle: str | None = None,
    is_verified: bool = False,
    category: str = "Others",
    brand_hashtag: str = "#BeteDires"
) -> str:
    """
    Formats extracted data into the standardized Bete Dires template.
    The verification line is conditional (only shown if is_verified is True).
    """
    item = html.escape(data.get("item") or "እቃ")
    location = html.escape(data.get("location") or "ጎንደር")
    phone = html.escape(data.get("phone") or "N/A")
    price = html.escape(data.get("price") or "N/A")
    inbox = data.get("inbox") or ""
    condition = html.escape(data.get("condition") or "ያገለገለ")

    target_handle = channel_handle or os.getenv("TARGET_GROUP", "@BeteDires_Main")
    clean_handle = target_handle.replace("@", "")

    # Category tag
    category_tags = {
        "Cosmetics": "#Cosmetics #Beauty",
        "Electronics": "#Electronics #Tech",
        "Vehicles": "#Cars #Vehicles",
        "Furniture": "#Furniture #Home",
        "Clothing": "#Fashion #Clothing",
        "House/Rent": "#RealEstate #Rent",
        "Others": "#Market"
    }
    cat_tag = category_tags.get(category, "#Market")

    lines = [
        f"🏷 <b>{item}</b>",
        f"🔖 <b>መለያ ቁጥር: </b> <code>{serial}</code>",
        "━━━━━━━━━━━━━━━━━━━",
        f"ℹ️ <b>የእቃው ሁኔታ: </b> {condition}",
        f"📍 <b>ቦታ: </b> {location}",
        f"💰 <b>ዋጋ: </b> <code>{price}</code> <b>ብር </b>"
    ]

    if inbox and inbox.strip() and inbox.strip() != "-":
        safe_inbox = html.escape(inbox.replace("@", ""))
        lines.append(f"👤 <b>ሻጭ inbox:</b> @{safe_inbox}")

    lines.append(f"📞 <b>ስልክ ቁጥር:</b> {phone}")
    lines.append("━━━━━━━━━━━━━━━━━━━")

    # Conditional verification line
    if is_verified:
        lines.append(f"✅ <i>የተረጋገጠ እቃ በ @{clean_handle}</i>")
    else:
        lines.append(f"🛍 <i>በ @{clean_handle} የቀረበ</i>")

    lines.append("")
    lines.append(f"{cat_tag} {brand_hashtag}")

    return "\n".join(lines)
