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
        pass

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
