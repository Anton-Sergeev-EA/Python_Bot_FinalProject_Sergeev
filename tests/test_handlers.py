"""
Тесты для обработчиков бота
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from telegram import Update, Message, Chat, User as TelegramUser, CallbackQuery
from telegram.ext import ContextTypes, CallbackContext

from bot.handlers.start import start_command, help_command
from bot.handlers.ads import start_ad_creation
from bot.handlers.feedback import start_feedback
from bot.handlers.moderation import start_moderation
from database.crud import user_crud
from database.connection import db
from config import settings


class TestBotHandlers:
    """Тесты обработчиков бота."""

    def setup_method(self):
        """Настройка перед каждым тестом."""
        # Мокаем базу данных.
        self.mock_session = Mock()
        self.mock_user = Mock()
        self.mock_user.id = 1
        self.mock_user.telegram_id = 123456789
        self.mock_user.username = "test_user"
        self.mock_user.first_name = "Test"

        # Мокаем get_session.
        self.session_patch = patch('database.connection.db.get_session')
        self.mock_get_session = self.session_patch.start()
        self.mock_get_session.return_value.__enter__.return_value = self.mock_session

    def teardown_method(self):
        """Очистка после каждого теста."""
        self.session_patch.stop()

    @pytest.mark.asyncio
    async def test_start_command(self):
        """Тест команды /start."""
        # Создаем моки.
        mock_update = AsyncMock(spec=Update)
        mock_context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)

        # Мокаем пользователя.
        mock_user = Mock(spec=TelegramUser)
        mock_user.id = 123456789
        mock_user.username = "test_user"
        mock_user.first_name = "Test"
        mock_user.last_name = "User"

        mock_update.effective_user = mock_user
        mock_update.message = AsyncMock(spec=Message)
        mock_update.message.reply_text = AsyncMock()

        # Мокаем get_or_create.
        with patch('bot.handlers.start.user_crud.get_or_create') as mock_get_or_create:
            mock_get_or_create.return_value = self.mock_user

            # Вызываем команду.
            await start_command(mock_update, mock_context)

            # Проверяем что функция была вызвана.
            assert mock_update.message.reply_text.called

            # Проверяем аргументы вызова.
            call_args = mock_update.message.reply_text.call_args
            assert call_args is not None
            assert "Добро пожаловать" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_start_command_callback(self):
        """Тест /start через callback."""
        # Создаем моки.
        mock_update = AsyncMock(spec=Update)
        mock_context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)

        # Мокаем callback query.
        mock_callback = AsyncMock(spec=CallbackQuery)
        mock_callback.edit_message_text = AsyncMock()

        mock_update.callback_query = mock_callback
        mock_update.effective_user = Mock(spec=TelegramUser)
        mock_update.effective_user.id = 123456789
        mock_update.effective_user.username = "test_user"

        # Мокаем get_or_create.
        with patch('bot.handlers.start.user_crud.get_or_create') as mock_get_or_create:
            mock_get_or_create.return_value = self.mock_user

            # Вызываем команду.
            await start_command(mock_update, mock_context)

            # Проверяем что функция была вызвана.
            assert mock_callback.edit_message_text.called

    @pytest.mark.asyncio
    async def test_help_command(self):
        """Тест команды /help."""
        # Создаем моки.
        mock_update = AsyncMock(spec=Update)
        mock_context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)

        mock_update.message = AsyncMock(spec=Message)
        mock_update.message.reply_text = AsyncMock()

        # Вызываем команду.
        await help_command(mock_update, mock_context)

        # Проверяем что функция была вызвана.
        assert mock_update.message.reply_text.called

        # Проверяем содержание помощи.
        call_args = mock_update.message.reply_text.call_args
        assert call_args is not None
        help_text = call_args[0][0]
        assert "/start" in help_text
        assert "/help" in help_text
        assert "/menu" in help_text

    @pytest.mark.asyncio
    async def test_start_ad_creation(self):
        """Тест начала создания объявления."""
        # Создаем моки.
        mock_update = AsyncMock(spec=Update)
        mock_context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)
        mock_context.user_data = {}

        # Мокаем callback query.
        mock_callback = AsyncMock(spec=CallbackQuery)
        mock_callback.edit_message_text = AsyncMock()
        mock_callback.answer = AsyncMock()

        mock_update.callback_query = mock_callback
        mock_update.effective_user = Mock(spec=TelegramUser)
        mock_update.effective_user.id = 123456789

        # Мокаем проверку лимита объявлений.
        mock_ads = []
        with patch('bot.handlers.ads.ad_crud.get_user_ads') as mock_get_ads:
            mock_get_ads.return_value = mock_ads

            # Вызываем обработчик.
            result = await start_ad_creation(mock_update, mock_context)

            # Проверяем.
            assert mock_callback.edit_message_text.called
            assert 'Создание нового объявления' in mock_callback.edit_message_text.call_args[0][0]
            assert result == 1  # AD_CREATION.TITLE.

    @pytest.mark.asyncio
    async def test_start_ad_creation_limit_exceeded(self):
        """Тест превышения лимита объявлений."""
        # Создаем моки.
        mock_update = AsyncMock(spec=Update)
        mock_context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)

        # Мокаем callback query.
        mock_callback = AsyncMock(spec=CallbackQuery)
        mock_callback.answer = AsyncMock()

        mock_update.callback_query = mock_callback
        mock_update.effective_user = Mock(spec=TelegramUser)
        mock_update.effective_user.id = 123456789

        # Мокаем проверку лимита - возвращаем 10 объявлений (лимит).
        mock_ads = [Mock() for _ in range(10)]
        with patch('bot.handlers.ads.ad_crud.get_user_ads') as mock_get_ads:
            mock_get_ads.return_value = mock_ads

            # Вызываем обработчик.
            result = await start_ad_creation(mock_update, mock_context)

            # Проверяем что пользователь получил предупреждение.
            assert mock_callback.answer.called
            assert "лимит" in mock_callback.answer.call_args[0][0].lower()
            assert result == -1  # END

    @pytest.mark.asyncio
    async def test_start_feedback(self):
        """Тест начала системы отзывов."""
        # Создаем моки.
        mock_update = AsyncMock(spec=Update)
        mock_context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)

        # Мокаем callback query.
        mock_callback = AsyncMock(spec=CallbackQuery)
        mock_callback.edit_message_text = AsyncMock()

        mock_update.callback_query = mock_callback

        # Вызываем обработчик.
        await start_feedback(mock_update, mock_context)

        # Проверяем.
        assert mock_callback.edit_message_text.called
        assert 'Система отзывов' in mock_callback.edit_message_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_start_moderation_admin(self):
        """Тест панели модерации для админа."""
        # Сохраняем оригинальные админы.
        original_admins = settings.ADMIN_IDS
        settings.ADMIN_IDS = [123456789]

        try:
            # Создаем моки.
            mock_update = AsyncMock(spec=Update)
            mock_context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)

            # Мокаем callback query.
            mock_callback = AsyncMock(spec=CallbackQuery)
            mock_callback.edit_message_text = AsyncMock()

            mock_update.callback_query = mock_callback
            mock_update.effective_user = Mock(spec=TelegramUser)
            mock_update.effective_user.id = 123456789

            # Мокаем функции базы данных.
            with patch('bot.handlers.moderation.moderation_crud.get_pending_ads_count') as mock_count:
                mock_count.return_value = 5

                with patch('bot.handlers.moderation.ad_crud.Ad') as mock_ad:
                    # Вызываем обработчик.
                    await start_moderation(mock_update, mock_context)

                    # Проверяем.
                    assert mock_callback.edit_message_text.called
                    assert 'Панель модерации' in mock_callback.edit_message_text.call_args[0][0]

        finally:
            # Восстанавливаем оригинальные настройки.
            settings.ADMIN_IDS = original_admins

    @pytest.mark.asyncio
    async def test_start_moderation_non_admin(self):
        """Тест панели модерации для не-админа."""
        # Создаем моки.
        mock_update = AsyncMock(spec=Update)
        mock_context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)

        # Мокаем callback query.
        mock_callback = AsyncMock(spec=CallbackQuery)
        mock_callback.answer = AsyncMock()

        mock_update.callback_query = mock_callback
        mock_update.effective_user = Mock(spec=TelegramUser)
        mock_update.effective_user.id = 999999999  # Не админ.

        # Мокаем проверку прав.
        with patch('bot.handlers.moderation.user_crud.is_admin') as mock_is_admin:
            mock_is_admin.return_value = False

            # Вызываем обработчик.
            await start_moderation(mock_update, mock_context)

            # Проверяем что пользователь получил отказ.
            assert mock_callback.answer.called
            assert "нет прав" in mock_callback.answer.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Тест обработки ошибок в командах."""
        # Создаем моки.
        mock_update = AsyncMock(spec=Update)
        mock_context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)

        mock_update.message = AsyncMock(spec=Message)
        mock_update.message.reply_text = AsyncMock()

        # Имитируем ошибку в get_or_create.
        with patch('bot.handlers.start.user_crud.get_or_create') as mock_get_or_create:
            mock_get_or_create.side_effect = Exception("Test error")

            # Вызываем команду.
            await start_command(mock_update, mock_context)

            # Проверяем что пользователь получил сообщение об ошибке.
            assert mock_update.message.reply_text.called
            call_args = mock_update.message.reply_text.call_args
            assert "ошибка" in call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_context_user_data(self):
        """Тест использования user_data в контексте."""
        # Создаем моки.
        mock_update = AsyncMock(spec=Update)
        mock_context = AsyncMock(spec=ContextTypes.DEFAULT_TYPE)
        mock_context.user_data = {'test_key': 'test_value'}

        mock_update.message = AsyncMock(spec=Message)
        mock_update.message.reply_text = AsyncMock()

        # Проверяем что user_data сохраняется.
        assert 'test_key' in mock_context.user_data
        assert mock_context.user_data['test_key'] == 'test_value'


class TestInputValidation:
    """Тесты валидации ввода."""

    @pytest.mark.asyncio
    async def test_ad_title_validation(self):
        """Тест валидации названия объявления."""
        from bot.utils import validator

        # Корректные названия.
        valid_titles = [
            "Велосипед горный",
            "Ноутбук MacBook Pro",
            "Книга 'Война и мир'",
            "123 Тестовое название"
        ]

        for title in valid_titles:
            is_valid, result = validator.validate_title(title)
            assert is_valid
            assert result == title.strip()

        # Некорректные названия.
        invalid_cases = [
            ("", "Название не может быть пустым"),
            ("ab", "Название слишком короткое"),
            ("a" * 201, "Название слишком длинное"),
            ("http://spam.com", "Название содержит запрещенные элементы"),
            ("@username", "Название содержит запрещенные элементы"),
            ("#hashtag", "Название содержит запрещенные элементы")
        ]

        for title, expected_error in invalid_cases:
            is_valid, result = validator.validate_title(title)
            assert not is_valid
            assert expected_error in result

    @pytest.mark.asyncio
    async def test_price_validation(self):
        """Тест валидации цены."""
        from bot.utils import validator

        # Корректные цены.
        valid_prices = [
            ("1000", 1000.0),
            ("1500.50", 1500.5),
            ("1,000.50", 1000.5),
            ("500 руб", 500.0),
            (" 750 ", 750.0)
        ]

        for price_str, expected in valid_prices:
            is_valid, result = validator.validate_price(price_str)
            assert is_valid
            assert result == expected

        # Некорректные цены.
        invalid_prices = [
            "abc",
            "",
            "-100",
            "1000000000",  # Превышение MAX_PRICE.
            "not a number"
        ]

        for price_str in invalid_prices:
            is_valid, result = validator.validate_price(price_str)
            assert not is_valid

    @pytest.mark.asyncio
    async def test_contact_info_validation(self):
        """Тест валидации контактной информации."""
        from bot.utils import validator

        # Корректные контакты.
        valid_contacts = [
            "@username",
            "+7 999 123-45-67",
            "email@example.com",
            "@username, +79991234567",
            "Telegram: @username Телефон: 89991234567"
        ]

        for contact in valid_contacts:
            is_valid, result = validator.validate_contact_info(contact)
            assert is_valid

        # Некорректные контакты.
        invalid_contacts = [
            "",
            "abc",
            "just text",
            "   ",
            "no contact info here"
        ]

        for contact in invalid_contacts:
            is_valid, result = validator.validate_contact_info(contact)
            assert not is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
