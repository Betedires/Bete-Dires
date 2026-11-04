from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, Enum, text, UniqueConstraint
import enum
from datetime import datetime

from config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

class ItemStatus(str, enum.Enum):
    PENDING = "pending"
    POSTED = "posted"
    PARTIALLY_POSTED = "partially_posted"
    SOLD = "sold"
    SCHEDULED = "scheduled"

class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("category", "category_id_seq", name="uq_item_category_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    photo_file_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    price: Mapped[str] = mapped_column(String)
    location: Mapped[str] = mapped_column(String)
    phone: Mapped[str] = mapped_column(String)
    condition: Mapped[str] = mapped_column(String)
    username: Mapped[str] = mapped_column(String)
    
    category: Mapped[str] = mapped_column(String, nullable=True)
    category_id_seq: Mapped[int] = mapped_column(Integer, nullable=True) # Per-category sequence number
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.PENDING)
    channel_message_id: Mapped[int] = mapped_column(Integer, nullable=True)
    category_message_id: Mapped[int] = mapped_column(Integer, nullable=True)
    channel_chat_id: Mapped[str] = mapped_column(String, nullable=True) # Specific target channel handle/ID
    category_chat_id: Mapped[str] = mapped_column(String, nullable=True) # Specific category channel handle/ID
    scheduled_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    post_error: Mapped[str] = mapped_column(String, nullable=True) # Failure reason if publishing fails
    
    # Forwarder & Source Attribution
    source_chat_id: Mapped[str] = mapped_column(String, nullable=True)
    source_message_id: Mapped[int] = mapped_column(Integer, nullable=True)
    source_link: Mapped[str] = mapped_column(String, nullable=True)
    content_hash: Mapped[str] = mapped_column(String, nullable=True, index=True)

    # Trust & Ownership
    telegram_user_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    is_verified: Mapped[int] = mapped_column(Integer, default=0, index=True) # 1 if seller or item verified by admin
    expiry_warning_sent: Mapped[int] = mapped_column(Integer, default=0) # 1 if pre-expiry warning sent
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

class Settings(Base):
    __tablename__ = "settings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    expiry_days: Mapped[int] = mapped_column(Integer, default=7)

class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    language: Mapped[str] = mapped_column(String, default="am") # 'am' or 'en'
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SearchAlert(Base):
    __tablename__ = "search_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    query: Mapped[str] = mapped_column(String)
    normalized_query: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String, nullable=True)
    max_price: Mapped[float] = mapped_column(nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Seller(Base):
    __tablename__ = "sellers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    phone: Mapped[str] = mapped_column(String)
    username: Mapped[str] = mapped_column(String, nullable=True)
    id_photo_path: Mapped[str] = mapped_column(String, nullable=True) # Private path in secure_uploads/ids/
    status: Mapped[str] = mapped_column(String, default="pending", index=True) # 'pending', 'approved', 'rejected'
    rejection_reason: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(Integer, index=True)
    reporter_user_id: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending", index=True) # 'pending', 'resolved', 'dismissed'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    item_name: Mapped[str] = mapped_column(String)
    item_serial: Mapped[str] = mapped_column(String, nullable=True)
    item_quality: Mapped[str] = mapped_column(String, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    total_price: Mapped[str] = mapped_column(String, nullable=True)
    customer_city: Mapped[str] = mapped_column(String)
    customer_location: Mapped[str] = mapped_column(String)
    customer_phone: Mapped[str] = mapped_column(String, nullable=True)
    customer_note: Mapped[str] = mapped_column(String, nullable=True)
    telegram_target: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM settings"))
        count = result.scalar()
        if count == 0:
            session.add(Settings(id=1, expiry_days=7))
            await session.commit()
