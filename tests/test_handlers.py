import pytest
from unittest.mock import AsyncMock, Mock, patch
from telegram import Update, Message, Chat, User, CallbackQuery
from telegram.ext import ContextTypes

from bot.handlers import ads, start, common
from database.models import AdStatus
from config.settings import settings


class TestAdsHandlers:

    @pytest.fixture
    def mock_update(self):
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 123456
        update.callback_query = Mock(spec=CallbackQuery)
        update.callback_query.data = "manage_ad_1"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        context.bot_data = {}
        return context

    @pytest.mark.asyncio
    async def test_manage_ad_valid_callback(self, mock_update, mock_context):
        with patch('bot.handlers.ads.get_ad_by_id') as mock_get_ad:
            mock_ad = Mock()
            mock_ad.id = 1
            mock_ad.user_id = 123
            mock_ad.created_at = "2024-01-01"
            mock_ad.text = "Test ad text"
            mock_ad.contact_info = "test@example.com"
            mock_ad.status = AdStatus.PENDING
            mock_ad.photo_url = None
            mock_get_ad.return_value = mock_ad

            original_admin_ids = settings.ADMIN_IDS
            settings.ADMIN_IDS = [123456]

            try:
                await ads.manage_ad(mock_update, mock_context)

                mock_update.callback_query.answer.assert_called_once()

                mock_update.callback_query.edit_message_text.assert_called_once()

            finally:
                settings.ADMIN_IDS = original_admin_ids

    @pytest.mark.asyncio
    async def test_manage_ad_invalid_callback_format(self, mock_update, mock_context):
        mock_update.callback_query.data = "invalid_format"

        await ads.manage_ad(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
        assert "❌ Произошла ошибка" in call_args

    @pytest.mark.asyncio
    async def test_manage_ad_non_numeric_ad_id(self, mock_update, mock_context):
        mock_update.callback_query.data = "manage_ad_abc"

        await ads.manage_ad(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_manage_ad_short_callback(self, mock_update, mock_context):
        mock_update.callback_query.data = "manage_ad"

        await ads.manage_ad(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_manage_ad_nonexistent_ad(self, mock_update, mock_context):
        with patch('bot.handlers.ads.get_ad_by_id') as mock_get_ad:
            mock_get_ad.return_value = None

            original_admin_ids = settings.ADMIN_IDS
            settings.ADMIN_IDS = [123456]

            try:
                await ads.manage_ad(mock_update, mock_context)

                mock_update.callback_query.edit_message_text.assert_called_once()
                call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
                assert "не найдено" in call_args

            finally:
                settings.ADMIN_IDS = original_admin_ids

    @pytest.mark.asyncio
    async def test_manage_ad_non_admin_user(self, mock_update, mock_context):
        mock_update.effective_user.id = 999999  # Non-admin

        with patch('bot.handlers.ads.get_ad_by_id') as mock_get_ad:
            mock_ad = Mock()
            mock_get_ad.return_value = mock_ad
            original_admin_ids = settings.ADMIN_IDS
            settings.ADMIN_IDS = [123456, 654321]

            try:
                await ads.manage_ad(mock_update, mock_context)

                mock_update.callback_query.edit_message_text.assert_called_once()
                call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
                assert "нет прав" in call_args

            finally:
                settings.ADMIN_IDS = original_admin_ids

    @pytest.mark.asyncio
    async def test_approve_ad_valid(self, mock_update, mock_context):
        mock_update.callback_query.data = "approve_ad_1"

        with patch('bot.handlers.ads.update_ad_status') as mock_update_status:
            mock_update_status.return_value = True

            await ads.approve_ad(mock_update, mock_context)

            mock_update.callback_query.edit_message_text.assert_called_once()
            call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
            assert "одобрено" in call_args

    @pytest.mark.asyncio
    async def test_approve_ad_invalid_format(self, mock_update, mock_context):
        mock_update.callback_query.data = "approve_ad"

        await ads.approve_ad(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()
        assert "Ошибка" in mock_update.callback_query.edit_message_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_reject_ad_valid(self, mock_update, mock_context):
        mock_update.callback_query.data = "reject_ad_1"

        with patch('bot.handlers.ads.update_ad_status') as mock_update_status:
            mock_update_status.return_value = True

            await ads.reject_ad(mock_update, mock_context)

            mock_update.callback_query.edit_message_text.assert_called_once()
            call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
            assert "отклонено" in call_args

    @pytest.mark.asyncio
    async def test_confirm_delete_ad(self, mock_update, mock_context):
        mock_update.callback_query.data = "delete_ad_1"

        await ads.confirm_delete_ad(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args[0][0]
        assert "уверены" in call_args
        assert "удалить" in call_args


class TestConversationHandler:

    @pytest.mark.asyncio
    async def test_conversation_flow(self):
        """Тестирование полного потока диалога создания объявления."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.reply_text = AsyncMock()
        update.message.text = "Новое объявление"
        update.message.from_user = Mock(spec=User)
        update.message.from_user.id = 123456

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}

        result = await ads.start_ad_creation(update, context)
        assert result == 0
        update.message.reply_text.assert_called_with("📝 Отправьте текст объявления:")

        update.message.text = "Тестовое объявление"
        update.message.contact = None

        result = await ads.receive_ad_text(update, context)
        assert result == 1
        assert context.user_data['ad_text'] == "Тестовое объявление"
        update.message.reply_text.assert_called_with(
            "📱 Отправьте контактные данные или нажмите кнопку ниже:",
            reply_markup=ANY
        )

        mock_contact = Mock()
        mock_contact.phone_number = "+79991234567"
        update.message.contact = mock_contact
        update.message.text = None

        with patch('bot.handlers.ads.create_ad') as mock_create_ad:
            mock_create_ad.return_value = Mock(id=1)

            result = await ads.receive_contact(update, context)
            assert result == -1

            mock_create_ad.assert_called_once_with(
                user_id=123456,
                text="Тестовое объявление",
                contact_info="+79991234567"
            )

            update.message.reply_text.assert_called_with(
                "✅ Объявление создано и отправлено на модерацию!"
            )

    @pytest.mark.asyncio
    async def test_conversation_flow_with_photo(self):
        """Тестирование диалога с добавлением фото"""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.reply_text = AsyncMock()
        update.message.from_user = Mock(spec=User)
        update.message.from_user.id = 123456

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}

        result = await ads.start_ad_creation(update, context)
        assert result == 0

        update.message.text = "Объявление с фото"
        update.message.photo = [Mock(file_id="photo123")]

        result = await ads.receive_ad_text(update, context)
        assert result == 1
        assert context.user_data['ad_text'] == "Объявление с фото"
        assert context.user_data['photo'] == "photo123"

        update.message.text = "test@example.com"
        update.message.contact = None

        with patch('bot.handlers.ads.create_ad') as mock_create_ad:
            mock_create_ad.return_value = Mock(id=1)

            result = await ads.receive_contact(update, context)
            assert result == -1
            mock_create_ad.assert_called_once_with(
                user_id=123456,
                text="Объявление с фото",
                contact_info="test@example.com",
                photo_url="photo123"
            )

    @pytest.mark.asyncio
    async def test_conversation_cancel_during_flow(self):
        """Тестирование отмены диалога на разных этапах."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.reply_text = AsyncMock()
        update.message.text = "/cancel"

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {"ad_text": "черновик"}

        result = await ads.cancel(update, context)
        assert result == -1
        assert "ad_text" not in context.user_data
        update.message.reply_text.assert_called_with(
            "Операция отменена.",
            reply_markup=None
        )

        update.message.reply_text.reset_mock()
        context.user_data = {"ad_text": "черновик", "photo": "photo123"}

        result = await ads.cancel(update, context)
        assert result == -1
        assert context.user_data == {}
        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_conversation_invalid_input(self):
        """Тестирование обработки некорректного ввода."""
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.reply_text = AsyncMock()
        update.message.from_user = Mock(spec=User)

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}

        update.message.text = ""
        result = await ads.receive_ad_text(update, context)
        assert result == 0
        update.message.reply_text.assert_called_with(
            "❌ Текст не может быть пустым. Попробуйте снова:"
        )

        update.message.text = "a" * 5000
        update.message.reply_text.reset_mock()

        result = await ads.receive_ad_text(update, context)
        assert result == 0
        update.message.reply_text.assert_called_with(
            "❌ Текст слишком длинный. Максимум 4096 символов. Попробуйте снова:"
        )

        update.message.text = ""
        update.message.contact = None

        result = await ads.receive_contact(update, context)
        assert result == 1
        update.message.reply_text.assert_called_with(
            "❌ Контактные данные не могут быть пустыми. Попробуйте снова:"
        )

    @pytest.mark.asyncio
    async def test_conversation_cancel(self):
        update = Mock(spec=Update)
        update.message = Mock(spec=Message)
        update.message.reply_text = AsyncMock()

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)

        await ads.cancel(update, context)

        update.message.reply_text.assert_called_once_with(
            "Операция отменена.",
            reply_markup=None
        )


class TestEdgeCases:

    @pytest.mark.asyncio
    async def test_empty_callback_data(self):
        update = Mock(spec=Update)
        update.callback_query = Mock(spec=CallbackQuery)
        update.callback_query.data = ""
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)

        await ads.manage_ad(update, context)

        update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_none_callback_query(self):
        update = Mock(spec=Update)
        update.callback_query = None

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)

        await ads.manage_ad(update, context)

    @pytest.mark.asyncio
    async def test_large_ad_id(self):
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=User)
        update.effective_user.id = 123456
        update.callback_query = Mock(spec=CallbackQuery)
        update.callback_query.data = "manage_ad_9999999999"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()

        context = Mock(spec=ContextTypes.DEFAULT_TYPE)

        with patch('bot.handlers.ads.get_ad_by_id') as mock_get_ad:
            mock_get_ad.return_value = None

            original_admin_ids = settings.ADMIN_IDS
            settings.ADMIN_IDS = [123456]

            try:
                await ads.manage_ad(update, context)

                mock_update.callback_query.answer.assert_called_once()

            finally:
                settings.ADMIN_IDS = original_admin_ids
