import asyncio
from sqlalchemy import text
from database import engine

async def migrate():
    print("Starting manual migration...")
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE items ADD COLUMN category_id_seq INTEGER"))
            print("Successfully added category_id_seq column.")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                pass
            else:
                print(f"Migration error: {e}")
                
        try:
            await conn.execute(text("ALTER TABLE items ADD COLUMN category_message_id INTEGER"))
            print("Successfully added category_message_id column.")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("Column category_message_id already exists, skipping.")
            else:
                print(f"Migration error: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
