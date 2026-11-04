import os
import hmac
import hashlib
import time
import secrets
from dotenv import load_dotenv

load_dotenv()

# Branding
BRAND_NAME = os.getenv("BRAND_NAME", "Bete Dires (ቤተ ድረስ)")
BRAND_HASHTAG = os.getenv("BRAND_HASHTAG", "#BeteDires")
WATERMARK_TEXT = os.getenv("WATERMARK_TEXT", "Bete Dires")

# Bot & Telegram Channels
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@BeteDires_Main")
ADMIN_USERNAME_TEMPLATE = os.getenv("ADMIN_USERNAME", "@BeteDires_admin")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./betedires.db")

# 7 Dedicated Channels Mapping
CATEGORY_CHANNELS = {
    "Cosmetics": os.getenv("CHANNEL_COSMETICS", "@BeteDires_Cosmetics"),
    "Electronics": os.getenv("CHANNEL_ELECTRONICS", "@BeteDires_Electronics"),
    "Furniture": os.getenv("CHANNEL_FURNITURE", "@BeteDires_Furniture"),
    "Clothing": os.getenv("CHANNEL_CLOTHING", "@BeteDires_Clothing"),
    "House/Rent": os.getenv("CHANNEL_HOUSERENT", "@BeteDires_House"),
    "Vehicles": os.getenv("CHANNEL_VEHICLES", "@BeteDires_Vehicles"),
    "Others": CHANNEL_ID
}

# Category Shorthand Serial Codes (e.g. 050 CO 012)
ITEM_SHORTHANDS = {
    "Cosmetics": "CO",
    "Electronics": "EL",
    "Vehicles": "VE",
    "Furniture": "FU",
    "Clothing": "CL",
    "House/Rent": "HR",
    "Others": "OT"
}

# Category-Specific Hashtags
CATEGORY_TAGS = {
    "Cosmetics": "#Cosmetics #Beauty",
    "Electronics": "#Electronics #Tech",
    "Vehicles": "#Cars #Vehicles",
    "Furniture": "#Furniture #Home",
    "Clothing": "#Fashion #Clothing",
    "House/Rent": "#RealEstate #Rent",
    "Others": "#Market"
}

# Dashboard Server Settings
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8001"))

# Authentication & Security
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "betedires_default_secret_key_change_me")
SESSION_COOKIE_NAME = "betedires_session"
SESSION_MAX_AGE_SECONDS = 86400 * 7 # 7 days

def hash_password(plain_password: str) -> str:
    """Computes a SHA-256 hash for storing in ADMIN_PASSWORD_HASH."""
    return hashlib.sha256(plain_password.encode("utf-8")).hexdigest()

def verify_admin_password(plain_password: str) -> bool:
    """Verifies input password against ADMIN_PASSWORD_HASH or plain ADMIN_PASSWORD."""
    if ADMIN_PASSWORD_HASH:
        input_hash = hash_password(plain_password)
        return hmac.compare_digest(input_hash, ADMIN_PASSWORD_HASH)
    return hmac.compare_digest(plain_password, ADMIN_PASSWORD)

def create_session_token() -> str:
    """Generates an HMAC-signed session token containing user, timestamp, and unique nonce."""
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(4)
    payload = f"admin:{timestamp}:{nonce}"
    sig = hmac.new(SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"

def verify_session_token(token: str) -> bool:
    """Validates session token signature and expiration."""
    if not token or ":" not in token:
        return False
    parts = token.split(":")
    if len(parts) == 4:
        user, ts_str, nonce, sig = parts
        payload = f"{user}:{ts_str}:{nonce}"
    elif len(parts) == 3:
        user, ts_str, sig = parts
        payload = f"{user}:{ts_str}"
    else:
        return False
        
    if user != "admin":
        return False
    try:
        ts = int(ts_str)
        if time.time() - ts > SESSION_MAX_AGE_SECONDS or ts > time.time() + 300:
            return False
    except ValueError:
        return False
    expected_sig = hmac.new(SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected_sig)

def get_csrf_token(session_token: str) -> str:
    """Generates a CSRF token bound to the active session token."""
    if not session_token:
        return ""
    return hmac.new(SESSION_SECRET.encode("utf-8"), f"csrf:{session_token}".encode("utf-8"), hashlib.sha256).hexdigest()

def verify_csrf_token(csrf_token: str, session_token: str) -> bool:
    """Verifies that the CSRF token matches the session."""
    if not csrf_token or not session_token:
        return False
    expected = get_csrf_token(session_token)
    return hmac.compare_digest(csrf_token, expected)
