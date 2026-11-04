import asyncio
from sqlalchemy import select
from database import AsyncSessionLocal, Item, engine

async def backfill():
    print("Starting robust ID Backfill...")
    async with AsyncSessionLocal() as session:
        # Get all items ordered by ID
        result = await session.execute(select(Item).order_by(Item.id.asc()))
        all_items = result.scalars().all()
        
        if not all_items:
            print("No items found to backfill.")
            return

        cat_counters = {}
        for item in all_items:
            # Ensure category is set
            if not item.category:
                item.category = "Others"
            
            # Increment counter for this category
            cat_counters[item.category] = cat_counters.get(item.category, 0) + 1
            item.category_id_seq = cat_counters[item.category]
            
        await session.commit()
        print(f"Success! Backfilled {len(all_items)} items.")

if __name__ == "__main__":
    asyncio.run(backfill())
