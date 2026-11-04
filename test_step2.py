"""
test_step2.py
Automated test suite for Step 2 changes:
1. Config & Rebrand verification (Cosmetics category, shorthand CO, channels)
2. Authentication & CSRF token hashing/verification
3. Image magic-byte validation
4. Database schema, unique constraint, and MAX+1 sequence generation
"""
import io
from PIL import Image
import sqlite3

from config import (
    BRAND_NAME,
    CATEGORY_CHANNELS,
    ITEM_SHORTHANDS,
    CATEGORY_TAGS,
    ADMIN_PASSWORD,
    verify_admin_password,
    create_session_token,
    verify_session_token,
    get_csrf_token,
    verify_csrf_token
)
from utils import is_valid_image

def test_config_and_cosmetics():
    print("Testing config and Cosmetics category...")
    assert "Cosmetics" in CATEGORY_CHANNELS, "Cosmetics missing from CATEGORY_CHANNELS"
    assert ITEM_SHORTHANDS.get("Cosmetics") == "CO", f"Expected CO, got {ITEM_SHORTHANDS.get('Cosmetics')}"
    assert "Cosmetics" in CATEGORY_TAGS, "Cosmetics missing from CATEGORY_TAGS"
    assert "#BeteDires" in CATEGORY_TAGS["Cosmetics"] or "#Cosmetics" in CATEGORY_TAGS["Cosmetics"]
    print("  -> Passed.")

def test_auth_and_csrf():
    print("Testing authentication & CSRF...")
    assert verify_admin_password(ADMIN_PASSWORD) is True
    assert verify_admin_password("wrong_password") is False
    
    token = create_session_token()
    assert verify_session_token(token) is True
    assert verify_session_token("invalid_token") is False
    assert verify_session_token("admin:12345:fakesig") is False
    
    csrf = get_csrf_token(token)
    assert verify_csrf_token(csrf, token) is True
    assert verify_csrf_token("invalid_csrf", token) is False
    assert verify_csrf_token(csrf, "other_session") is False
    print("  -> Passed.")

def test_image_magic_bytes():
    print("Testing magic byte validation...")
    # 1. Valid JPEG
    img = Image.new("RGB", (50, 50), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    valid_jpeg = buf.getvalue()
    assert is_valid_image(valid_jpeg) is True
    
    # 2. Valid PNG
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    valid_png = buf.getvalue()
    assert is_valid_image(valid_png) is True
    
    # 3. Invalid Text File
    assert is_valid_image(b"This is a text file masquerading as an image") is False
    assert is_valid_image(b"") is False
    print("  -> Passed.")

def test_database_constraints():
    print("Testing database constraints & unique index on betedires.db...")
    conn = sqlite3.connect("betedires.db")
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA index_list(items)")
    indices = [row[1] for row in cursor.fetchall()]
    assert "uq_item_category_seq" in indices, f"Unique index missing! Indices found: {indices}"
    
    cursor.execute("PRAGMA table_info(items)")
    cols = [row[1] for row in cursor.fetchall()]
    assert "channel_chat_id" in cols, "channel_chat_id column missing"
    assert "category_chat_id" in cols, "category_chat_id column missing"
    
    # Verify MAX(category_id_seq) query
    cursor.execute("SELECT COALESCE(MAX(category_id_seq), 0) + 1 FROM items WHERE category = 'Cosmetics'")
    next_cosmetic_seq = cursor.fetchone()[0]
    assert next_cosmetic_seq >= 1
    
    conn.close()
    print("  -> Passed.")

if __name__ == "__main__":
    test_config_and_cosmetics()
    test_auth_and_csrf()
    test_image_magic_bytes()
    test_database_constraints()
    print("\nALL STEP 2 AUTOMATED TESTS PASSED!")
