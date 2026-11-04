import os
import sys

# Ensure root and telegram_forwarder are in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FWD_DIR = os.path.join(BASE_DIR, "telegram_forwarder")
for p in [BASE_DIR, FWD_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from parser import (
    parse_source_text,
    detect_category,
    evaluate_confidence,
    normalize_text,
    compute_content_hash,
    format_target_text
)

PASS = "\u2705"
FAIL = "\u274c"
_results = []

def check(label, expr):
    ok = bool(expr)
    _results.append((ok, label))
    icon = PASS if ok else FAIL
    print(f"  {icon}  {label}")
    return ok

def run_tests():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("\n=== Testing parser.py ===")

    # 1. Parsing Real-World Format with Emojis and 'ሺ'
    sample_text = """የሚሸጠው እቃ :- አይፎን 12 ፕሩ ማክስ
🟡 ዋጋ እና አድራሻ :- 65 ሺ ብር (ጎንደር አራዳ)
🟡 የባለቤቱ ቁጥር :- +251918765432
🟡 የባለቤቱ Inbox :- @seller_gondar
🟡 የእቃው መለያ ቁጥር :- 1234
"""
    parsed = parse_source_text(sample_text)
    check("parse_source_text: extracts item name correctly", "አይፎን 12 ፕሩ ማክስ" in parsed["item"])
    check("parse_source_text: converts 65 ሺ to 65,000", "65,000" in parsed["price"])
    check("parse_source_text: extracts location from parentheses", "ጎንደር አራዳ" in parsed["location"])
    check("parse_source_text: extracts clean phone number", "+251918765432" in parsed["phone"])
    check("parse_source_text: extracts username inbox", "@seller_gondar" in parsed["inbox"])

    # 2. Category Detection for all categories
    check("detect_category: Cosmetics (ሽቶ)", detect_category("ጥሩ ሽቶ የሚሸጥ", "ሽቶ") == "Cosmetics")
    check("detect_category: Electronics (ቴሌቪዥን)", detect_category("ስማርት ቴሌቪዥን", "ቲቪ") == "Electronics")
    check("detect_category: Vehicles (መኪና)", detect_category("ቶዮታ ያሪስ መኪና", "ያሪስ") == "Vehicles")
    check("detect_category: Furniture (ሶፋ)", detect_category("የሳሎን ሶፋ እና ጠረጴዛ", "ሶፋ") == "Furniture")
    check("detect_category: Clothing (ጫማ)", detect_category("የወንዶች ጫማ እና ሱሪ", "ጫማ") == "Clothing")
    check("detect_category: House/Rent (ቤት ኪራይ)", detect_category("የሚከራይ ቤት ጎንደር", "ቤት") == "House/Rent")
    check("detect_category: Others (fallback)", detect_category("የተለያየ እቃ", "እቃ") == "Others")

    # 3. Confidence Assessment
    high_conf_data = {
        "item": "Samsung Galaxy S22",
        "price": "45,000",
        "phone": "+251911223344",
        "inbox": "@seller"
    }
    is_high, reason = evaluate_confidence(high_conf_data)
    check("evaluate_confidence: high confidence when all fields present", is_high and reason == "high_confidence")

    missing_price_data = {
        "item": "Samsung Galaxy S22",
        "price": "N/A",
        "phone": "+251911223344"
    }
    is_high, reason = evaluate_confidence(missing_price_data)
    check("evaluate_confidence: flags missing price", not is_high and reason == "missing_or_invalid_price")

    missing_phone_data = {
        "item": "Samsung Galaxy S22",
        "price": "45,000",
        "phone": "invalid"
    }
    is_high, reason = evaluate_confidence(missing_phone_data)
    check("evaluate_confidence: flags invalid phone", not is_high and reason == "missing_or_invalid_phone")

    # 4. Normalization and Content Hashing
    t1 = "  አይፎን 12  (65 ሺ) ! "
    t2 = "አይፎን 12 (65 ሺ)"
    check("normalize_text: strips excess whitespace and punctuation", normalize_text(t1) == normalize_text(t2))

    h1 = compute_content_hash(t1, b"sample_image_bytes")
    h2 = compute_content_hash(t2, b"sample_image_bytes")
    check("compute_content_hash: deterministic and matches for normalized text", h1 == h2)

    h3 = compute_content_hash(t1, b"different_image_bytes")
    check("compute_content_hash: different image produces different hash", h1 != h3)

    # 5. Format Target Text & Conditional Verification
    unverified_text = format_target_text(high_conf_data, serial="050 EL 015", is_verified=False)
    check("format_target_text: does NOT say 'የተረጋገጠ እቃ' when is_verified=False", "የተረጋገጠ እቃ" not in unverified_text)
    check("format_target_text: includes serial number", "050 EL 015" in unverified_text)

    verified_text = format_target_text(high_conf_data, serial="050 EL 015", is_verified=True)
    check("format_target_text: includes 'የተረጋገጠ እቃ' only when is_verified=True", "የተረጋገጠ እቃ" in verified_text)

    print("\n" + "=" * 55)
    passed = sum(1 for ok, _ in _results if ok)
    total = len(_results)
    print(f"Parser Tests: {passed}/{total} passed.")
    if passed != total:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
