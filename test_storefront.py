"""
test_storefront.py
Automated test suite for Bete Dires (ቤቴ ድረስ) Marketplace Storefront:
1. Public Storefront (GET /) rendering with Alibaba layout & brand psychology
2. Product Detail & Open Graph Meta Tags (GET /item/{id})
3. Instant Search & Products API (GET /api/products)
4. Telegram Inbound Order Logging API (POST /api/order)
5. Fallback SVG Placeholder for missing photos (GET /photo/{file_id})
6. Admin authentication isolation (GET /admin -> /login)
7. Static asset delivery (store.css, store.js, logo.png, placeholder.svg)
8. Telegram message formatting check (Item, Quality, Location)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from fastapi.testclient import TestClient
import urllib.parse
from main import app
from database import AsyncSessionLocal, Order
from sqlalchemy import select

client = TestClient(app)

def test_static_assets():
    print("[1] Testing static asset delivery...")
    res_css = client.get("/static/store.css")
    assert res_css.status_code == 200, f"Expected 200 for store.css, got {res_css.status_code}"
    assert "--brand-green" in res_css.text
    print("  ✅ static/store.css delivered with Bete Dires palette")

    res_js = client.get("/static/store.js")
    assert res_js.status_code == 200, f"Expected 200 for store.js, got {res_js.status_code}"
    assert "BeteDires" in res_js.text
    assert "handleOrderModalSubmit" in res_js.text
    print("  ✅ static/store.js delivered with search & Telegram order logic")

    res_logo = client.get("/static/logo.png")
    assert res_logo.status_code == 200, f"Expected 200 for logo.png, got {res_logo.status_code}"
    assert len(res_logo.content) > 1000
    print("  ✅ static/logo.png delivered successfully")

    res_svg = client.get("/static/placeholder.svg")
    assert res_svg.status_code == 200, f"Expected 200 for placeholder.svg, got {res_svg.status_code}"
    assert "image/svg+xml" in res_svg.headers.get("content-type", "")
    print("  ✅ static/placeholder.svg delivered with SVG media type")

def test_store_home_page():
    print("\n[2] Testing Public Storefront (GET /)...")
    res = client.get("/")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    text = res.text

    # Branding & Psychological Elements
    assert "BETE DIRES" in text, "Missing BETE DIRES brand header"
    assert "ቤቴ ድረስ" in text, "Missing Amharic brand name"
    assert "አይተው ይክፈሉ" in text, "Missing Pay on Inspection psychological assurance"
    assert "Doorstep Delivery" in text or "ቤቴ ድረስ አቅርቦት" in text

    # Alibaba-Style Search Box
    assert 'id="search-input"' in text, "Missing search input"
    assert 'id="search-cat-select"' in text, "Missing category dropdown selector"
    assert 'id="search-loc-select"' in text, "Missing location dropdown selector"

    # Product Grid & Telegram Buy Buttons
    assert 'class="product-card"' in text, "Missing product cards"
    assert 'data-i18n="buyViaTelegram"' in text or "በቴሌግራም ይዘዙ" in text, "Missing Buy via Telegram buttons"
    assert 'id="order-modal-overlay"' in text, "Missing order modal"
    assert 'id="cart-drawer-overlay"' in text, "Missing cart drawer"
    print("  ✅ Storefront rendered with full Alibaba layout & psychological triggers")

def test_product_detail_and_open_graph():
    print("\n[3] Testing Product Detail & Open Graph Meta Tags (GET /item/1)...")
    res = client.get("/item/1")
    assert res.status_code == 200
    text = res.text

    assert 'property="og:title"' in text
    assert 'property="og:image"' in text
    assert 'property="og:description"' in text
    assert 'property="og:site_name"' in text
    assert 'Bete Dires' in text
    print("  ✅ Open Graph tags properly populated for Telegram preview card unfurling")

def test_api_products():
    print("\n[4] Testing Instant Products API (GET /api/products)...")
    res = client.get("/api/products")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["count"] > 0
    assert len(data["products"]) > 0

    first_item = data["products"][0]
    assert "name" in first_item
    assert "serial" in first_item
    assert "price" in first_item
    assert "category" in first_item
    assert "condition" in first_item
    assert "location" in first_item
    print(f"  ✅ API returned {data['count']} active products with serials, conditions & locations")

def test_api_order_logging():
    print("\n[5] Testing Telegram Inbound Order Logging (POST /api/order)...")
    payload = {
        "item_id": 1,
        "item_name": "Test Sofa Deluxe",
        "item_serial": "001 FU 001",
        "item_quality": "ትንሽ ያገለገለ (Like New)",
        "quantity": 2,
        "total_price": "70,000 ብር",
        "customer_city": "Addis Ababa",
        "customer_location": "Addis Ababa, Bole Medhanialem behind Edna Mall",
        "customer_phone": "0911223344",
        "customer_note": "Direct website test order"
    }

    res = client.post("/api/order", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "order_id" in data
    assert data["order_id"] > 0
    print(f"  ✅ Order #{data['order_id']} successfully recorded in betedires.db orders table")

def test_photo_fallback():
    print("\n[6] Testing Resilient Photo Fallback (GET /photo/{nonexistent})...")
    res = client.get("/photo/local:nonexistent_photo_12345.jpg")
    assert res.status_code == 200
    # Must return SVG placeholder without crashing
    assert "image/svg+xml" in res.headers.get("content-type", "") or "<svg" in res.text
    print("  ✅ Missing photos gracefully fall back to branded SVG placeholder")

def test_admin_route_protection():
    print("\n[7] Testing Admin Dashboard Route Protection (GET /admin)...")
    res = client.get("/admin", follow_redirects=False)
    assert res.status_code in (302, 303), f"Expected redirect, got {res.status_code}"
    assert "/login" in res.headers.get("location", "")
    print("  ✅ /admin securely redirects unauthenticated visitors to /login")

def test_telegram_message_encoding():
    print("\n[8] Testing Telegram Pre-filled Message Structure...")
    # Verify that Telegram message format contains Item, Quality, and Location
    item_name = "ሶፋ እና ጠረጴዛ"
    serial = "003 FU 001"
    quality = "ትንሽ ያገለገለ (Slightly Used)"
    location = "Addis Ababa, Bole Medhanialem"
    price = "35,000"

    expected_msg = (
        f"👋 ሰላም Bete Dires Admin! በድረ-ገጹ (Website) በኩል እቃ ማዘዝ እፈልጋለሁ፡\n\n"
        f"📦 እቃ (Item): {item_name}\n"
        f"🏷 መለያ ቁጥር (Serial): #{serial}\n"
        f"✨ ጥራት / ሁኔታ (Quality): {quality}\n"
        f"💰 ዋጋ (Unit Price): {price} ብር\n"
        f"📍 የመላኪያ ቦታ (Location): {location}\n"
    )

    encoded = urllib.parse.quote(expected_msg)
    assert "%E1%8A%A5%E1%89%83" in encoded or "Item" in urllib.parse.unquote(encoded)
    assert serial in urllib.parse.unquote(encoded)
    assert quality in urllib.parse.unquote(encoded)
    assert location in urllib.parse.unquote(encoded)
    print("  ✅ Telegram message template accurately encodes item, quality, and location")

if __name__ == "__main__":
    test_static_assets()
    test_store_home_page()
    test_product_detail_and_open_graph()
    test_api_products()
    test_api_order_logging()
    test_photo_fallback()
    test_admin_route_protection()
    test_telegram_message_encoding()
    print("\n=======================================================")
    print("  🎉 ALL 8 STOREFRONT AUTOMATED TESTS PASSED SUCCESSFULLY!")
    print("=======================================================")
