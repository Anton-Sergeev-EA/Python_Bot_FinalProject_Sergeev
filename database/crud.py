from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func, extract
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from .models import (
    User, Ad, AdStatus, Category, Message, Feedback,
    SearchQuery, Notification, ModerationQueue, UserRole
)
from .connection import db

logger = logging.getLogger(__name__)


# User CRUD operations.
class UserCRUD:
    @staticmethod
    def get_or_create(session: Session, telegram_id: int, **kwargs):
        """Get user by telegram_id or create if not exists."""
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(telegram_id=telegram_id, **kwargs)
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

    @staticmethod
    def get_by_id(session: Session, user_id: int):
        """Get user by id."""
        return session.query(User).filter(User.id == user_id).first()

    @staticmethod
    def update_user(session: Session, user_id: int, **kwargs):
        """Update user information."""
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            session.commit()
            session.refresh(user)
        return user

    @staticmethod
    def is_admin(session: Session, telegram_id: int):
        """Check if user is admin."""
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        return user and user.role in [UserRole.ADMIN, UserRole.MODERATOR]


# Ad CRUD operations.
class AdCRUD:
    @staticmethod
    def create_ad(session: Session, owner_id: int, **kwargs):
        """Create new ad."""
        ad = Ad(owner_id=owner_id, **kwargs)
        session.add(ad)
        session.commit()
        session.refresh(ad)

        # Add to moderation queue.
        moderation_entry = ModerationQueue(ad_id=ad.id)
        session.add(moderation_entry)
        session.commit()

        return ad

    @staticmethod
    def get_ad(session: Session, ad_id: int):
        """Get ad by id."""
        return session.query(Ad).filter(Ad.id == ad_id).first()

    @staticmethod
    def get_user_ads(session: Session, user_id: int, status: Optional[AdStatus] = None):
        """Get all ads for a user, optionally filtered by status."""
        query = session.query(Ad).filter(Ad.owner_id == user_id)
        if status:
            query = query.filter(Ad.status == status)
        return query.order_by(desc(Ad.created_at)).all()

    @staticmethod
    def update_ad(session: Session, ad_id: int, user_id: int, **kwargs):
        """Update ad (only owner can update)."""
        ad = session.query(Ad).filter(
            Ad.id == ad_id,
            Ad.owner_id == user_id
        ).first()

        if not ad:
            return None

        # If changing content, need re-moderation.
        if any(key in kwargs for key in ['title', 'description', 'price', 'location', 'contact_info']):
            ad.status = AdStatus.PENDING

        for key, value in kwargs.items():
            if hasattr(ad, key):
                setattr(ad, key, value)

        session.commit()
        session.refresh(ad)
        return ad

    @staticmethod
    def delete_ad(session: Session, ad_id: int, user_id: int):
        """Delete ad (only owner can delete)."""
        ad = session.query(Ad).filter(
            Ad.id == ad_id,
            Ad.owner_id == user_id
        ).first()

        if ad:
            session.delete(ad)
            session.commit()
            return True
        return False

    @staticmethod
    def search_ads(
            session: Session,
            keywords: Optional[str] = None,
            location: Optional[str] = None,
            min_price: Optional[float] = None,
            max_price: Optional[float] = None,
            category_id: Optional[int] = None,
            limit: int = 50,
            offset: int = 0
    ):
        """Search ads with filters."""
        query = session.query(Ad).filter(Ad.status == AdStatus.APPROVED)

        if keywords:
            search_pattern = f"%{keywords}%"
            query = query.filter(
                or_(
                    Ad.title.ilike(search_pattern),
                    Ad.description.ilike(search_pattern)
                )
            )

        if location:
            query = query.filter(Ad.location.ilike(f"%{location}%"))

        if min_price is not None:
            query = query.filter(Ad.price >= min_price)

        if max_price is not None:
            query = query.filter(Ad.price <= max_price)

        if category_id:
            query = query.filter(Ad.category_id == category_id)

        return query.order_by(desc(Ad.created_at)).limit(limit).offset(offset).all()

    @staticmethod
    def moderate_ad(
            session: Session,
            ad_id: int,
            status: AdStatus,
            moderator_id: int,
            rejection_reason: Optional[str] = None
    ):
        """Moderate ad."""
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            return None

        ad.status = status
        ad.moderator_id = moderator_id
        ad.moderated_at = func.now()

        if status == AdStatus.REJECTED:
            ad.rejection_reason = rejection_reason

        # Remove from moderation queue.
        session.query(ModerationQueue).filter(ModerationQueue.ad_id == ad_id).delete()

        session.commit()
        session.refresh(ad)

        # Create notification for owner.
        if status in [AdStatus.APPROVED, AdStatus.REJECTED]:
            NotificationCRUD.create_notification(
                session,
                user_id=ad.owner_id,
                type=f"ad_{status.value}",
                title="Статус объявления изменен",
                content=f"Ваше объявление '{ad.title}' было {'одобрено' if status == AdStatus.APPROVED else 'отклонено'}",
                data={"ad_id": ad.id, "status": status.value}
            )

        return ad


# Message CRUD operations.
class MessageCRUD:
    @staticmethod
    def send_message(
            session: Session,
            sender_id: int,
            receiver_id: int,
            content: str,
            ad_id: Optional[int] = None
    ):
        """Send message between users."""
        message = Message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            ad_id=ad_id
        )
        session.add(message)
        session.commit()
        session.refresh(message)

        # Create notification for receiver.
        NotificationCRUD.create_notification(
            session,
            user_id=receiver_id,
            type="new_message",
            title="Новое сообщение",
            content=f"Вы получили новое сообщение",
            data={
                "message_id": message.id,
                "sender_id": sender_id,
                "ad_id": ad_id
            }
        )

        return message

    @staticmethod
    def get_conversation(
            session: Session,
            user1_id: int,
            user2_id: int,
            limit: int = 50,
            offset: int = 0
    ):
        """Get conversation between two users."""
        return session.query(Message).filter(
            or_(
                and_(Message.sender_id == user1_id, Message.receiver_id == user2_id),
                and_(Message.sender_id == user2_id, Message.receiver_id == user1_id)
            )
        ).order_by(Message.created_at).limit(limit).offset(offset).all()

    @staticmethod
    def get_unread_count(session: Session, user_id: int):
        """Get count of unread messages for user."""
        return session.query(Message).filter(
            Message.receiver_id == user_id,
            Message.is_read == False
        ).count()


# Feedback CRUD operations.
class FeedbackCRUD:
    @staticmethod
    def create_feedback(
            session: Session,
            user_id: int,
            rating: int,
            comment: Optional[str] = None,
            ad_id: Optional[int] = None,
            feedback_type: str = "ad"
    ):
        """Create feedback."""
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")

        feedback = Feedback(
            user_id=user_id,
            ad_id=ad_id,
            rating=rating,
            comment=comment,
            type=feedback_type
        )
        session.add(feedback)
        session.commit()
        session.refresh(feedback)
        return feedback

    @staticmethod
    def get_ad_feedback(session: Session, ad_id: int):
        """Get all feedback for an ad."""
        return session.query(Feedback).filter(
            Feedback.ad_id == ad_id,
            Feedback.type == "ad"
        ).order_by(desc(Feedback.created_at)).all()

    @staticmethod
    def get_bot_feedback(session: Session, limit: int = 100):
        """Get all feedback for the bot."""
        return session.query(Feedback).filter(
            Feedback.type == "bot"
        ).order_by(desc(Feedback.created_at)).limit(limit).all()

    @staticmethod
    def get_average_rating(session: Session, ad_id: int):
        """Get average rating for an ad."""
        result = session.query(
            func.avg(Feedback.rating).label('average'),
            func.count(Feedback.id).label('count')
        ).filter(
            Feedback.ad_id == ad_id,
            Feedback.type == "ad"
        ).first()

        return result.average, result.count


# Search Query CRUD operations.
class SearchQueryCRUD:
    @staticmethod
    def save_search_query(
            session: Session,
            user_id: int,
            keywords: Optional[str] = None,
            location: Optional[str] = None,
            min_price: Optional[float] = None,
            max_price: Optional[float] = None,
            category_id: Optional[int] = None
    ):
        """Save user's search query for notifications."""
        query = SearchQuery(
            user_id=user_id,
            keywords=keywords,
            location=location,
            min_price=min_price,
            max_price=max_price,
            category_id=category_id
        )
        session.add(query)
        session.commit()
        session.refresh(query)
        return query

    @staticmethod
    def get_user_queries(session: Session, user_id: int):
        """Get all search queries for a user."""
        return session.query(SearchQuery).filter(
            SearchQuery.user_id == user_id,
            SearchQuery.is_active == True
        ).all()

    @staticmethod
    def get_queries_for_notification(session: Session, ad: Ad):
        """Get all search queries that match an ad."""
        queries = session.query(SearchQuery).filter(
            SearchQuery.is_active == True,
            SearchQuery.last_notified < ad.created_at  # Only notify once per ad
        )

        matching_queries = []
        for query in queries:
            matches = True

            if query.keywords:
                matches = matches and (
                        query.keywords.lower() in ad.title.lower() or
                        query.keywords.lower() in ad.description.lower()
                )

            if query.location:
                matches = matches and (
                        query.location.lower() in ad.location.lower()
                )

            if query.min_price:
                matches = matches and (ad.price >= query.min_price)

            if query.max_price:
                matches = matches and (ad.price <= query.max_price)

            if query.category_id:
                matches = matches and (ad.category_id == query.category_id)

            if matches:
                matching_queries.append(query)

        return matching_queries


# Notification CRUD operations.
class NotificationCRUD:
    @staticmethod
    def create_notification(
            session: Session,
            user_id: int,
            type: str,
            content: str,
            title: Optional[str] = None,
            data: Optional[Dict] = None
    ):
        """Create notification for user."""
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            content=content,
            data=data or {}
        )
        session.add(notification)
        session.commit()
        session.refresh(notification)
        return notification

    @staticmethod
    def get_unread_notifications(session: Session, user_id: int, limit: int = 50):
        """Get unread notifications for user."""
        return session.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).order_by(desc(Notification.created_at)).limit(limit).all()

    @staticmethod
    def mark_as_read(session: Session, notification_id: int, user_id: int):
        """Mark notification as read."""
        notification = session.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()

        if notification:
            notification.is_read = True
            session.commit()
            return True
        return False

    @staticmethod
    def mark_all_as_read(session: Session, user_id: int):
        """Mark all notifications as read for user."""
        session.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).update({"is_read": True})
        session.commit()


# Moderation CRUD operations.
class ModerationCRUD:
    @staticmethod
    def get_pending_ads_count(session: Session):
        """Get count of ads pending moderation."""
        return session.query(ModerationQueue).count()

    @staticmethod
    def get_next_ad_to_moderate(session: Session):
        """Get next ad to moderate (highest priority first)."""
        return session.query(ModerationQueue).join(Ad).order_by(
            desc(ModerationQueue.priority),
            ModerationQueue.created_at
        ).first()

    @staticmethod
    def assign_ad_to_moderator(session: Session, ad_id: int, moderator_id: int):
        """Assign ad to moderator."""
        queue_entry = session.query(ModerationQueue).filter(
            ModerationQueue.ad_id == ad_id
        ).first()

        if queue_entry:
            queue_entry.assigned_to = moderator_id
            session.commit()
            return True
        return False


# Initialize CRUD classes.
user_crud = UserCRUD()
ad_crud = AdCRUD()
message_crud = MessageCRUD()
feedback_crud = FeedbackCRUD()
search_query_crud = SearchQueryCRUD()
notification_crud = NotificationCRUD()
moderation_crud = ModerationCRUD()
