"""
Тесты для моделей базы данных
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, User, Ad, AdStatus, Category, Message, Feedback
from database.connection import db


class TestDatabaseModels:
    """Тесты моделей базы данных."""

    @classmethod
    def setup_class(cls):
        """Настройка тестового окружения."""
        # Создаем тестовую базу данных в памяти.
        cls.engine = create_engine('sqlite:///:memory:')
        cls.Session = sessionmaker(bind=cls.engine)

        # Создаем таблицы.
        Base.metadata.create_all(cls.engine)

    @classmethod
    def teardown_class(cls):
        """Очистка после тестов."""
        Base.metadata.drop_all(cls.engine)

    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.session = self.Session()

    def teardown_method(self):
        """Очистка после каждого теста."""
        self.session.rollback()
        self.session.close()

    def test_create_user(self):
        """Тест создания пользователя."""
        user = User(
            telegram_id=123456789,
            username="test_user",
            first_name="Test",
            last_name="User"
        )

        self.session.add(user)
        self.session.commit()

        assert user.id is not None
        assert user.telegram_id == 123456789
        assert user.username == "test_user"
        assert user.created_at is not None

    def test_create_ad(self):
        """Тест создания объявления."""
        # Создаем пользователя.
        user = User(
            telegram_id=123456789,
            username="ad_owner"
        )
        self.session.add(user)
        self.session.commit()

        # Создаем категорию.
        category = Category(
            name="Электроника",
            description="Техника и гаджеты"
        )
        self.session.add(category)
        self.session.commit()

        # Создаем объявление.
        ad = Ad(
            title="Тестовое объявление",
            description="Описание тестового объявления",
            price=1000.50,
            location="Москва",
            contact_info="@test_user",
            owner_id=user.id,
            category_id=category.id,
            status=AdStatus.PENDING
        )

        self.session.add(ad)
        self.session.commit()

        assert ad.id is not None
        assert ad.title == "Тестовое объявление"
        assert ad.price == 1000.50
        assert ad.status == AdStatus.PENDING
        assert ad.owner == user
        assert ad.category == category

    def test_ad_status_enum(self):
        """Тест статусов объявлений."""
        assert AdStatus.DRAFT.value == "draft"
        assert AdStatus.PENDING.value == "pending"
        assert AdStatus.APPROVED.value == "approved"
        assert AdStatus.REJECTED.value == "rejected"
        assert AdStatus.RENTED.value == "rented"
        assert AdStatus.ARCHIVED.value == "archived"

    def test_create_message(self):
        """Тест создания сообщения."""
        # Создаем пользователей.
        sender = User(telegram_id=111111111, username="sender")
        receiver = User(telegram_id=222222222, username="receiver")

        self.session.add(sender)
        self.session.add(receiver)
        self.session.commit()

        # Создаем сообщение.
        message = Message(
            content="Тестовое сообщение",
            sender_id=sender.id,
            receiver_id=receiver.id
        )

        self.session.add(message)
        self.session.commit()

        assert message.id is not None
        assert message.content == "Тестовое сообщение"
        assert not message.is_read
        assert message.sender == sender
        assert message.receiver == receiver

    def test_create_feedback(self):
        """Тест создания отзыва."""
        # Создаем пользователя.
        user = User(telegram_id=333333333, username="feedback_user")
        self.session.add(user)
        self.session.commit()

        # Создаем отзыв.
        feedback = Feedback(
            user_id=user.id,
            rating=5,
            comment="Отличный сервис!",
            type="bot"
        )

        self.session.add(feedback)
        self.session.commit()

        assert feedback.id is not None
        assert feedback.rating == 5
        assert feedback.comment == "Отличный сервис!"
        assert feedback.type == "bot"
        assert feedback.user == user

    def test_relationships(self):
        """Тест связей между моделями."""
        # Создаем пользователя.
        user = User(telegram_id=444444444, username="rel_user")
        self.session.add(user)
        self.session.commit()

        # Создаем несколько объявлений.
        ad1 = Ad(
            title="Объявление 1",
            description="Описание 1",
            price=100,
            location="Локация 1",
            contact_info="@user",
            owner_id=user.id,
            status=AdStatus.APPROVED
        )

        ad2 = Ad(
            title="Объявление 2",
            description="Описание 2",
            price=200,
            location="Локация 2",
            contact_info="@user",
            owner_id=user.id,
            status=AdStatus.APPROVED
        )

        self.session.add_all([ad1, ad2])
        self.session.commit()

        # Проверяем связи.
        assert len(user.ads) == 2
        assert ad1 in user.ads
        assert ad2 in user.ads
        assert ad1.owner == user
        assert ad2.owner == user

    def test_timestamps(self):
        """Тест временных меток."""
        user = User(telegram_id=555555555, username="timestamp_user")
        self.session.add(user)
        self.session.commit()

        # Проверяем created_at.
        assert user.created_at is not None
        assert isinstance(user.created_at, datetime)

        # Обновляем пользователя.
        original_updated = user.updated_at
        user.username = "updated_user"
        self.session.commit()

        # Проверяем updated_at.
        assert user.updated_at is not None
        if original_updated:
            assert user.updated_at > original_updated

    def test_category_activation(self):
        """Тест активации категорий."""
        category = Category(
            name="Тестовая категория",
            description="Описание",
            is_active=False
        )

        self.session.add(category)
        self.session.commit()

        assert not category.is_active

        # Активируем категорию.
        category.is_active = True
        self.session.commit()

        assert category.is_active

    def test_message_read_status(self):
        """Тест статуса прочтения сообщения."""
        sender = User(telegram_id=666666666)
        receiver = User(telegram_id=777777777)

        self.session.add_all([sender, receiver])
        self.session.commit()

        message = Message(
            content="Непрочитанное сообщение",
            sender_id=sender.id,
            receiver_id=receiver.id,
            is_read=False
        )

        self.session.add(message)
        self.session.commit()

        assert not message.is_read

        # Отмечаем как прочитанное.
        message.is_read = True
        self.session.commit()

        assert message.is_read

    def test_feedback_rating_validation(self):
        """Тест валидации рейтинга в отзывах."""
        user = User(telegram_id=888888888)
        self.session.add(user)
        self.session.commit()

        # Должны работать оценки от 1 до 5.
        for rating in [1, 2, 3, 4, 5]:
            feedback = Feedback(
                user_id=user.id,
                rating=rating,
                type="bot"
            )
            self.session.add(feedback)

        self.session.commit()

        # Проверяем что создалось 5 отзывов.
        feedbacks = self.session.query(Feedback).filter_by(user_id=user.id).all()
        assert len(feedbacks) == 5

        # Проверяем рейтинги.
        ratings = [f.rating for f in feedbacks]
        assert set(ratings) == {1, 2, 3, 4, 5}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
