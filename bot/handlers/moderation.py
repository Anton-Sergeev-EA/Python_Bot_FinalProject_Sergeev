from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from telegram.constants import ParseMode
import logging
from datetime import datetime, timedelta
from typing import Optional

from bot.keyboards import inline_keyboards
from bot.utils import formatter
from database.crud import (
    user_crud, ad_crud, moderation_crud,
    notification_crud
)
from database.models import AdStatus, UserRole
from database.connection import db
from config import settings

logger = logging.getLogger(__name__)


async def start_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start moderation interface."""
    user = update.effective_user

    # Check if user is moderator/admin
    if user.id not in settings.ADMIN_IDS:
        with db.get_session() as session:
            if not user_crud.is_admin(session, user.id):
                await update.callback_query.answer(
                    "У вас нет прав для модерации",
                    show_alert=True
                )
                return

    try:
        with db.get_session() as session:
            # Get moderation stats.
            pending_count = moderation_crud.get_pending_ads_count(session)

            # Get recent moderated ads.
            recent_moderated = session.query(ad_crud.Ad).filter(
                ad_crud.Ad.status.in_([AdStatus.APPROVED, AdStatus.REJECTED]),
                ad_crud.Ad.moderated_at >= datetime.now() - timedelta(days=1)
            ).count()

            stats_text = (
                "👑 *Панель модерации*\n\n"
                f"📊 *Статистика за 24 часа:*\n"
                f"• ⏳ Ожидают проверки: {pending_count}\n"
                f"• ✅ Одобрено: {recent_moderated}\n"
                f"• ❌ Отклонено: {recent_moderated}\n\n"
                "Выберите действие:"
            )

            keyboard = [
                [
                    InlineKeyboardButton("👁️ Проверить объявления", callback_data="moderate_next"),
                    InlineKeyboardButton("📋 Список ожидания", callback_data="moderation_queue")
                ],
                [
                    InlineKeyboardButton("📊 Статистика", callback_data="moderation_stats"),
                    InlineKeyboardButton("⚙️ Настройки", callback_data="moderation_settings")
                ],
                [
                    InlineKeyboardButton("👤 Пользователи", callback_data="moderation_users"),
                    InlineKeyboardButton("📝 Все объявления", callback_data="moderation_all_ads")
                ],
                [
                    InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
                ]
            ]

            if update.callback_query:
                await update.callback_query.edit_message_text(
                    stats_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.message.reply_text(
                    stats_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

    except Exception as e:
        logger.error(f"Error in start_moderation: {e}")
        error_text = "😔 Произошла ошибка при загрузке панели модерации."
        if update.callback_query:
            await update.callback_query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)


async def moderate_next_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show next ad for moderation"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    try:
        with db.get_session() as session:
            # Get next ad in moderation queue.
            queue_entry = moderation_crud.get_next_ad_to_moderate(session)

            if not queue_entry:
                await query.edit_message_text(
                    "✅ *Нет объявлений для модерации*\n\n"
                    "Все объявления проверены! Отличная работа! 🎉",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=inline_keyboards.main_menu_keyboard()
                )
                return

            ad = queue_entry.ad
            ad_owner = ad.owner

            # Format ad for moderation.
            ad_text = formatter.format_ad_full({
                'id': ad.id,
                'title': ad.title,
                'description': ad.description,
                'price': ad.price,
                'location': ad.location,
                'contact_info': ad.contact_info,
                'created_at': ad.created_at,
                'status': ad.status.value
            }, show_contacts=True)

            # Add user info.
            user_info = (
                f"\n👤 *Информация о пользователе:*\n"
                f"• ID: `{ad_owner.telegram_id}`\n"
                f"• Username: @{ad_owner.username or 'Нет'}\n"
                f"• Имя: {ad_owner.first_name or 'Нет'}\n"
                f"• Всего объявлений: {len(ad_owner.ads) if hasattr(ad_owner, 'ads') else 0}\n"
                f"• Статус: {'✅ Активен' if not ad_owner.is_banned else '❌ Заблокирован'}"
            )

            full_text = f"👁️ *Модерация объявления*\n\n{ad_text}{user_info}"

            # Create moderation keyboard.
            keyboard = [
                [
                    InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_approve_{ad.id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_reject_{ad.id}")
                ],
                [
                    InlineKeyboardButton("⏸️ Отложить", callback_data=f"mod_defer_{ad.id}"),
                    InlineKeyboardButton("👤 Заблокировать автора", callback_data=f"mod_ban_{ad.id}")
                ],
                [
                    InlineKeyboardButton("📝 Редактировать", callback_data=f"mod_edit_{ad.id}"),
                    InlineKeyboardButton("💬 Написать автору", callback_data=f"mod_message_{ad.id}")
                ],
                [
                    InlineKeyboardButton("➡️ Следующее", callback_data="moderate_next"),
                    InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
                ]
            ]

            await query.edit_message_text(
                full_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True
            )

    except Exception as e:
        logger.error(f"Error in moderate_next_ad: {e}")
        await query.edit_message_text(
            "😔 Произошла ошибка при загрузке объявления для модерации.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )


async def approve_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve ad."""
    query = update.callback_query
    await query.answer()

    ad_id = int(query.data.split('_')[2])
    moderator_id = update.effective_user.id

    try:
        with db.get_session() as session:
            # Get moderator.
            moderator = user_crud.get_or_create(
                session,
                moderator_id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name
            )

            # Moderate ad.
            ad = ad_crud.moderate_ad(
                session,
                ad_id,
                AdStatus.APPROVED,
                moderator.id
            )

            if ad:
                # Send notification to owner.
                notification_crud.create_notification(
                    session,
                    user_id=ad.owner_id,
                    type="ad_approved",
                    title="Объявление одобрено",
                    content=f"Ваше объявление '{ad.title}' было одобрено и теперь видно в поиске.",
                    data={"ad_id": ad.id}
                )

                success_text = (
                    f"✅ *Объявление одобрено!*\n\n"
                    f"Объявление '{ad.title}' было успешно одобрено.\n"
                    f"Автор получил уведомление.\n\n"
                    f"🆔 ID объявления: `{ad.id}`"
                )

                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("➡️ Следующее", callback_data="moderate_next")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ])

                await query.edit_message_text(
                    success_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )

                logger.info(f"Ad {ad_id} approved by moderator {moderator_id}")
            else:
                await query.edit_message_text(
                    "❌ Объявление не найдено.",
                    reply_markup=inline_keyboards.main_menu_keyboard()
                )

    except Exception as e:
        logger.error(f"Error approving ad: {e}")
        await query.edit_message_text(
            "😔 Произошла ошибка при одобрении объявления.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )


async def reject_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start rejection process."""
    query = update.callback_query
    await query.answer()

    ad_id = int(query.data.split('_')[2])

    # Store ad_id in context.
    context.user_data['rejecting_ad_id'] = ad_id

    reject_text = (
        "❌ *Отклонение объявления*\n\n"
        "Пожалуйста, укажите причину отклонения:\n\n"
        "1. 🚫 Нарушает правила\n"
        "2. 📵 Неподходящий контент\n"
        "3. 💰 Некорректная цена\n"
        "4. 📍 Неверное местоположение\n"
        "5. 📞 Некорректные контакты\n"
        "6. ✏️ Требует редактирования\n"
        "7. ⚠️ Другая причина\n\n"
        "Введите причину отклонения:"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚫 Нарушает правила", callback_data=f"reject_reason_rules_{ad_id}"),
            InlineKeyboardButton("📵 Неподходящий контент", callback_data=f"reject_reason_content_{ad_id}")
        ],
        [
            InlineKeyboardButton("💰 Некорректная цена", callback_data=f"reject_reason_price_{ad_id}"),
            InlineKeyboardButton("📍 Неверное местоположение", callback_data=f"reject_reason_location_{ad_id}")
        ],
        [
            InlineKeyboardButton("📞 Некорректные контакты", callback_data=f"reject_reason_contacts_{ad_id}"),
            InlineKeyboardButton("✏️ Требует редактирования", callback_data=f"reject_reason_edit_{ad_id}")
        ],
        [
            InlineKeyboardButton("⚠️ Другая причина", callback_data=f"reject_reason_other_{ad_id}"),
            InlineKeyboardButton("◀️ Назад", callback_data=f"moderate_next")
        ]
    ])

    await query.edit_message_text(
        reject_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )


async def confirm_rejection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and process rejection."""
    query = update.callback_query
    await query.answer()

    # Parse rejection reason.
    parts = query.data.split('_')
    ad_id = int(parts[3])
    reason_type = parts[2]

    # Map reason type to text.
    reasons = {
        'rules': "Нарушает правила сервиса",
        'content': "Неподходящий контент",
        'price': "Некорректная цена",
        'location': "Неверное местоположение",
        'contacts': "Некорректные контакты",
        'edit': "Требует редактирования",
        'other': "Другая причина"
    }

    reason = reasons.get(reason_type, "Другая причина")

    moderator_id = update.effective_user.id

    try:
        with db.get_session() as session:
            # Get moderator.
            moderator = user_crud.get_or_create(
                session,
                moderator_id,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name
            )

            # Reject ad.
            ad = ad_crud.moderate_ad(
                session,
                ad_id,
                AdStatus.REJECTED,
                moderator.id,
                rejection_reason=reason
            )

            if ad:
                # Send notification to owner.
                notification_crud.create_notification(
                    session,
                    user_id=ad.owner_id,
                    type="ad_rejected",
                    title="Объявление отклонено",
                    content=f"Ваше объявление '{ad.title}' было отклонено. Причина: {reason}",
                    data={"ad_id": ad.id, "reason": reason}
                )

                success_text = (
                    f"❌ *Объявление отклонено!*\n\n"
                    f"Объявление '{ad.title}' было отклонено.\n"
                    f"Причина: {reason}\n\n"
                    f"Автор получил уведомление с причиной отклонения."
                )

                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("➡️ Следующее", callback_data="moderate_next")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
                ])

                await query.edit_message_text(
                    success_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )

                logger.info(f"Ad {ad_id} rejected by moderator {moderator_id}. Reason: {reason}")
            else:
                await query.edit_message_text(
                    "❌ Объявление не найдено.",
                    reply_markup=inline_keyboards.main_menu_keyboard()
                )

    except Exception as e:
        logger.error(f"Error rejecting ad: {e}")
        await query.edit_message_text(
            "😔 Произошла ошибка при отклонении объявления.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )


async def show_moderation_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show moderation queue."""
    query = update.callback_query
    await query.answer()

    try:
        with db.get_session() as session:
            # Get queue with ad details.
            queue_entries = session.query(moderation_crud.ModerationQueue).join(
                ad_crud.Ad
            ).order_by(
                moderation_crud.ModerationQueue.priority.desc(),
                moderation_crud.ModerationQueue.created_at
            ).limit(20).all()

            if not queue_entries:
                await query.edit_message_text(
                    "📭 *Очередь модерации пуста*\n\n"
                    "Нет объявлений, ожидающих проверки.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=inline_keyboards.main_menu_keyboard()
                )
                return

            queue_text = "⏳ *Очередь модерации*\n\n"

            for i, entry in enumerate(queue_entries, 1):
                ad = entry.ad
                priority_stars = "⭐" * entry.priority
                assigned = "👤" if entry.assigned_to else "🔓"

                queue_text += (
                    f"{i}. {priority_stars} *{formatter.escape_markdown(ad.title)}*\n"
                    f"   🆔 `{ad.id}` • {assigned} • 🕐 {formatter.time_ago(ad.created_at)}\n\n"
                )

            # Create keyboard with quick actions.
            keyboard_rows = []
            for entry in queue_entries[:5]:
                keyboard_rows.append([
                    InlineKeyboardButton(
                        f"👁️ {entry.ad.title[:15]}...",
                        callback_data=f"moderate_ad_{entry.ad.id}"
                    )
                ])

            keyboard_rows.append([
                InlineKeyboardButton("🔄 Обновить", callback_data="moderation_queue"),
                InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
            ])

            await query.edit_message_text(
                queue_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard_rows)
            )

    except Exception as e:
        logger.error(f"Error showing moderation queue: {e}")
        await query.edit_message_text(
            "😔 Произошла ошибка при загрузке очереди модерации.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )


async def moderation_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show moderation statistics."""
    query = update.callback_query
    await query.answer()

    try:
        with db.get_session() as session:
            # Get stats for last 7 days.
            seven_days_ago = datetime.now() - timedelta(days=7)

            # Approved count.
            approved_count = session.query(ad_crud.Ad).filter(
                ad_crud.Ad.status == AdStatus.APPROVED,
                ad_crud.Ad.moderated_at >= seven_days_ago
            ).count()

            # Rejected count.
            rejected_count = session.query(ad_crud.Ad).filter(
                ad_crud.Ad.status == AdStatus.REJECTED,
                ad_crud.Ad.moderated_at >= seven_days_ago
            ).count()

            # Pending count.
            pending_count = session.query(ad_crud.Ad).filter(
                ad_crud.Ad.status == AdStatus.PENDING
            ).count()

            # Average moderation time (simplified).
            avg_time_text = "~2 часа"

            # Top moderators (last 7 days).
            top_moderators = session.query(
                user_crud.User.username,
                user_crud.User.first_name,
                func.count(ad_crud.Ad.id).label('moderated_count')
            ).join(
                ad_crud.Ad, ad_crud.Ad.moderator_id == user_crud.User.id
            ).filter(
                ad_crud.Ad.moderated_at >= seven_days_ago
            ).group_by(
                user_crud.User.id
            ).order_by(
                func.count(ad_crud.Ad.id).desc()
            ).limit(5).all()

            stats_text = (
                "📊 *Статистика модерации (7 дней)*\n\n"
                f"• ✅ Одобрено: {approved_count}\n"
                f"• ❌ Отклонено: {rejected_count}\n"
                f"• ⏳ Ожидают: {pending_count}\n"
                f"• ⏱️ Среднее время: {avg_time_text}\n\n"
                "🏆 *Топ модераторов:*\n"
            )

            for i, (username, first_name, count) in enumerate(top_moderators, 1):
                name = username or first_name or f"Модератор {i}"
                stats_text += f"{i}. {name}: {count} объявлений\n"

            if not top_moderators:
                stats_text += "Нет данных\n"

            stats_text += "\n📈 *Общая статистика:*\n"

            # Total ads.
            total_ads = session.query(ad_crud.Ad).count()
            active_ads = session.query(ad_crud.Ad).filter(
                ad_crud.Ad.status == AdStatus.APPROVED
            ).count()

            stats_text += f"• 📝 Всего объявлений: {total_ads}\n"
            stats_text += f"• ✅ Активных: {active_ads}\n"
            stats_text += f"• 📊 Процент одобрения: {approved_count / (approved_count + rejected_count) * 100:.1f}%" if (
                                                                                                                                   approved_count + rejected_count) > 0 else "• 📊 Процент одобрения: N/A\n"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Обновить", callback_data="moderation_stats")],
                [InlineKeyboardButton("◀️ Назад", callback_data="admin_moderation")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ])

            await query.edit_message_text(
                stats_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Error showing moderation stats: {e}")
        await query.edit_message_text(
            "😔 Произошла ошибка при загрузке статистики.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )


async def moderate_specific_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Moderate specific ad by ID."""
    query = update.callback_query
    await query.answer()

    ad_id = int(query.data.split('_')[2])

    try:
        with db.get_session() as session:
            ad = ad_crud.get_ad(session, ad_id)

            if not ad:
                await query.edit_message_text(
                    "❌ Объявление не найдено.",
                    reply_markup=inline_keyboards.main_menu_keyboard()
                )
                return

            # Redirect to moderation view.
            context.user_data['current_moderation_ad'] = ad_id
            await moderate_next_ad(update, context)

    except Exception as e:
        logger.error(f"Error moderating specific ad: {e}")
        await query.edit_message_text(
            "😔 Произошла ошибка.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )


# Command handler for direct moderation.
async def mod_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mod command for moderators."""
    user = update.effective_user

    with db.get_session() as session:
        if not user_crud.is_admin(session, user.id) and user.id not in settings.ADMIN_IDS:
            await update.message.reply_text(
                "❌ У вас нет прав для использования этой команды."
            )
            return

    if context.args:
        try:
            ad_id = int(context.args[0])
            context.user_data['current_moderation_ad'] = ad_id
            await moderate_specific_ad(update, context)
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный ID объявления. Используйте: /mod <id>"
            )
    else:
        await start_moderation(update, context)


# Register handlers
def register_handlers(application):
    """Register all moderation handlers."""
    # Command handler.
    application.add_handler(CommandHandler("mod", mod_command))

    # Callback handlers.
    application.add_handler(CallbackQueryHandler(start_moderation, pattern="^admin_moderation$"))
    application.add_handler(CallbackQueryHandler(moderate_next_ad, pattern="^moderate_next$"))
    application.add_handler(CallbackQueryHandler(approve_ad, pattern="^mod_approve_"))
    application.add_handler(CallbackQueryHandler(reject_ad, pattern="^mod_reject_"))
    application.add_handler(CallbackQueryHandler(confirm_rejection, pattern="^reject_reason_"))
    application.add_handler(CallbackQueryHandler(show_moderation_queue, pattern="^moderation_queue$"))
    application.add_handler(CallbackQueryHandler(moderation_stats, pattern="^moderation_stats$"))
    application.add_handler(CallbackQueryHandler(moderate_specific_ad, pattern="^moderate_ad_"))
