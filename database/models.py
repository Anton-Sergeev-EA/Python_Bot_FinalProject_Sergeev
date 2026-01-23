from sqlalchemy import (
    Column, Integer, String, Float, Text, Boolean,
    DateTime, ForeignKey, Table, Enum, JSON
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class UserRole(enum.Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class AdStatus(enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RENTED = "rented"
    ARCHIVED = "archived"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone_number = Column(String(20))
    role = Column(Enum(UserRole), default=UserRole.USER)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships.
    ads = relationship("Ad", back_populates="owner", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="user", cascade="all, delete-orphan")
    search_queries = relationship("SearchQuery", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ads = relationship("Ad", back_populates="category")


class Ad(Base):
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    price = Column(Float, nullable=False)
    location = Column(String(200), nullable=False)
    contact_info = Column(Text, nullable=False)
    status = Column(Enum(AdStatus), default=AdStatus.PENDING)
    rejection_reason = Column(Text)

    # Foreign keys.
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"))
    moderator_id = Column(Integer, ForeignKey("users.id"))

    # Timestamps.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    moderated_at = Column(DateTime(timezone=True))

    # Relationships.
    owner = relationship("User", foreign_keys=[owner_id], back_populates="ads")
    category = relationship("Category", back_populates="ads")
    moderator = relationship("User", foreign_keys=[moderator_id])
    messages = relationship("Message", back_populates="ad", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="ad", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)

    # Foreign keys.
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ad_id = Column(Integer, ForeignKey("ads.id"))

    # Timestamps.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships.
    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])
    ad = relationship("Ad", back_populates="messages")


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True)
    rating = Column(Integer, nullable=False)  # 1-5.
    comment = Column(Text)
    type = Column(String(50))  # 'ad' or 'bot'.

    # Foreign keys.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ad_id = Column(Integer, ForeignKey("ads.id"))

    # Timestamps.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships.
    user = relationship("User", back_populates="feedbacks")
    ad = relationship("Ad", back_populates="feedbacks")


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id = Column(Integer, primary_key=True)
    keywords = Column(String(200))
    location = Column(String(200))
    min_price = Column(Float)
    max_price = Column(Float)
    category_id = Column(Integer, ForeignKey("categories.id"))
    is_active = Column(Boolean, default=True)

    # Foreign key.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Timestamps.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_notified = Column(DateTime(timezone=True))

    # Relationships.
    user = relationship("User", back_populates="search_queries")
    category = relationship("Category")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    type = Column(String(50), nullable=False)  # 'new_ad', 'new_message', 'ad_approved', etc.
    title = Column(String(200))
    content = Column(Text, nullable=False)
    data = Column(JSON)  # Additional data in JSON format.
    is_read = Column(Boolean, default=False)

    # Foreign key.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Timestamps.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships.
    user = relationship("User", back_populates="notifications")


class ModerationQueue(Base):
    __tablename__ = "moderation_queue"

    id = Column(Integer, primary_key=True)
    ad_id = Column(Integer, ForeignKey("ads.id"), unique=True, nullable=False)
    priority = Column(Integer, default=1)  # 1-5, higher = more urgent.
    assigned_to = Column(Integer, ForeignKey("users.id"))

    # Timestamps.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships.
    ad = relationship("Ad")
    moderator = relationship("User", foreign_keys=[assigned_to])
