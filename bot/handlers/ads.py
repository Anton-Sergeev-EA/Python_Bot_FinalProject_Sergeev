import logging
from datetime import datetime
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database.crud import (
    get_ad_by_id,
    update_ad_status,
    delete_ad,
    get_pending_ads_count,
)
from database.models import AdStatus
from config.settings import settings

logger = logging.getLogger(__name__)

# Conversation states
AD_ACTION, CONFIRM_DELETE = range(2)


async def manage_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not query or not query.data:
        logger.warning("No callback query or data received")
        return

    await query.answer()

    try:
        parts = query.data.split('_')
        if len(parts) < 3:
            raise ValueError(f"Invalid callback data format: {query.data}")

        ad_id = int(parts[2])
        logger.debug(f"Processing ad_id: {ad_id}")

    except (IndexError, ValueError) as e:
        logger.warning(f"Invalid callback_data received: {query.data}. Error: {e}")
        await query.edit_message_text(
            "❌ Произошла ошибка при обработке запроса. Пожалуйста, попробуйте еще раз."
        )
        return

    context.user_data['current_ad_id'] = ad_id

    ad = get_ad_by_id(ad_id)
    if not ad:
        await query.edit_message_text(
            "❌ Объявление не найдено. Возможно, оно было удалено."
        )
        return

    user_id = update.effective_user.id
    if user_id not in settings.ADMIN_IDS:
        await query.edit_message_text(
            "⛔ У вас нет прав для управления объявлениями."
        )
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_ad_{ad_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_ad_{ad_id}"),
        ],
        [
            InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_ad_{ad_id}"),
            InlineKeyboardButton("📝 Редактировать", callback_data=f"edit_ad_{ad_id}"),
        ],
        [
            InlineKeyboardButton("🔙 Назад к списку", callback_data="back_to_list"),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    ad_text = (
        f"📋 <b>Объявление #{ad_id}</b>\n"
        f"👤 Пользователь: {ad.user_id}\n"
        f"📅 Дата: {ad.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"📝 Текст: {ad.text[:200]}...\n"
        f"🔍 Контакты: {ad.contact_info}\n"
        f"📊 Статус: {ad.status.value}\n"
    )

    if ad.photo_url:
        ad_text += f"🖼️ Фото: {ad.photo_url}\n"

    await query.edit_message_text(
        ad_text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )


async def approve_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not query or not query.data:
        return

    await query.answer()

    try:
        ad_id = int(query.data.split('_')[2])
    except (IndexError, ValueError):
        logger.warning(f"Invalid approve callback: {query.data}")
        await query.edit_message_text("❌ Ошибка при обработке запроса.")
        return

    success = update_ad_status(ad_id, AdStatus.APPROVED)

    if success:
        await query.edit_message_text(
            f"✅ Объявление #{ad_id} одобрено и опубликовано."
        )
        logger.info(f"Ad {ad_id} approved by admin")
    else:
        await query.edit_message_text(
            f"❌ Не удалось одобрить объявление #{ad_id}."
        )


async def reject_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not query or not query.data:
        return

    await query.answer()

    try:
        ad_id = int(query.data.split('_')[2])
    except (IndexError, ValueError):
        logger.warning(f"Invalid reject callback: {query.data}")
        await query.edit_message_text("❌ Ошибка при обработке запроса.")
        return

    success = update_ad_status(ad_id, AdStatus.REJECTED)

    if success:
        await query.edit_message_text(
            f"❌ Объявление #{ad_id} отклонено."
        )
        logger.info(f"Ad {ad_id} rejected by admin")
    else:
        await query.edit_message_text(
            f"⚠️ Не удалось отклонить объявление #{ad_id}."
        )


async def confirm_delete_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not query or not query.data:
        return

    await query.answer()

    try:
        ad_id = int(query.data.split('_')[2])
    except (IndexError, ValueError):
        logger.warning(f"Invalid delete callback: {query.data}")
        await query.edit_message_text("❌ Ошибка при обработке запроса.")
        return

    context.user_data['ad_to_delete'] = ad_id

    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_yes_{ad_id}"),
            InlineKeyboardButton("❌ Нет, отменить", callback_data=f"confirm_delete_no_{ad_id}"),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"⚠️ Вы уверены, что хотите удалить объявление #{ad_id}?",
        reply_markup=reply_markup
    )


async def execute_delete_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute ad deletion after confirmation."""
    query = update.callback_query

    if not query or not query.data:
        return

    await query.answer()

    try:
        parts = query.data.split('_')
        action = parts[2]
        ad_id = int(parts[3])
    except (IndexError, ValueError):
        logger.warning(f"Invalid delete confirmation: {query.data}")
        await query.edit_message_text("❌ Ошибка при обработке запроса.")
        return

    if action == 'no':
        await query.edit_message_text("❌ Удаление отменено.")
        return

    success = delete_ad(ad_id)

    if success:
        await query.edit_message_text(
            f"🗑️ Объявление #{ad_id} успешно удалено."
        )
        logger.info(f"Ad {ad_id} deleted by admin")
    else:
        await query.edit_message_text(
            f"❌ Не удалось удалить объявление #{ad_id}."
        )


async def back_to_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    pending_count = get_pending_ads_count()

    await query.edit_message_text(
        f"📋 Список объявлений ({pending_count} на модерации)\n"
        "Используйте /ads для просмотра деталей каждого объявления."
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Операция отменена.",
        reply_markup=None
    )
    return ConversationHandler.END
