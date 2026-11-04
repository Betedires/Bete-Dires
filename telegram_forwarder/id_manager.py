import os
import sqlite3
from sqlalchemy import select, func

# Category Shorthands
ITEM_SHORTHANDS = {
    "Cosmetics": "CO",
    "Electronics": "EL",
    "Vehicles": "VE",
    "Furniture": "FU",
    "Clothing": "CL",
    "House/Rent": "HR",
    "Others": "OT"
}

def format_serial(item_id: int, category: str, category_seq: int) -> str:
    """
    Formats the standard serial format: [Global ID] [Category Code] [Category Seq].
    Example: 050 EL 015
    """
    code = ITEM_SHORTHANDS.get(category, "OT")
    global_str = str(item_id).zfill(3)
    seq_str = str(category_seq).zfill(3)
    return f"{global_str} {code} {seq_str}"

async def get_next_category_sequence(session, category: str) -> int:
    """
    Computes the next sequence number (MAX + 1) for a category within an active SQLAlchemy session.
    """
    from database import Item
    stmt = select(func.max(Item.category_id_seq)).where(Item.category == category)
    max_seq = await session.scalar(stmt)
    return (max_seq or 0) + 1

def get_next_id_sync(category: str = "Others", db_path: str = "betedires.db") -> tuple[int, int, str]:
    """
    Synchronous fallback for scripts/tests to query betedires.db directly.
    Returns (item_id, category_seq, formatted_serial).
    """
    if not os.path.exists(db_path):
        # Look one directory up if called from telegram_forwarder/
        alt = os.path.join("..", db_path)
        if os.path.exists(alt):
            db_path = alt

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get current max global id
    cur.execute("SELECT COALESCE(MAX(id), 0) FROM items")
    next_global_id = cur.fetchone()[0] + 1
    
    # Get current max category seq
    cur.execute("SELECT COALESCE(MAX(category_id_seq), 0) FROM items WHERE category = ?", (category,))
    next_cat_seq = cur.fetchone()[0] + 1
    
    conn.close()
    
    serial = format_serial(next_global_id, category, next_cat_seq)
    return next_global_id, next_cat_seq, serial

def get_next_id(category: str = "Others") -> str:
    """
    Backwards-compatible interface for existing callers:
    Generates the next real serial string using betedires.db instead of last_id.txt.
    """
    try:
        _, _, serial = get_next_id_sync(category)
        return serial
    except Exception:
        # Emergency fallback if DB is unreachable
        code = ITEM_SHORTHANDS.get(category, "OT")
        return f"999 {code} 999"

if __name__ == "__main__":
    print("Testing shared serial manager:")
    print("Cosmetics serial:", get_next_id("Cosmetics"))
    print("Electronics serial:", get_next_id("Electronics"))
