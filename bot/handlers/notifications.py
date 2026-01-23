from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from bot.keyboards import inline_keyboards
from bot.utils import formatter
from database.crud import notification_crud, user_crud, ad_crud, search_query_crud
from database.connection import db
from config import settings

logger = logging.getLogger(__name__)


async def show_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user notifications."""
    user = update.effective_user

    try:
        with db.get_session() as session:
            # Get user.
            db_user = user_crud.get_or_create(
                session,
                user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )

            # Get unread notifications.
            notifications = notification_crud.get_unread_notifications(
                session,
                db_user.id,
                limit=20
            )

            if not notifications:
                await update.callback_query.edit_message_text(
                    "📭 *Нет новых уведомлений*\n\n"
                    "Здесь будут появляться уведомления о новых сообщениях "
                    "и объявлениях, соответствующих вашим поискам.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=inline_keyboards.main_menu_keyboard()
                )
                return

            # Format notifications.
            notifications_text = "🔔 *Уведомления*\n\n"

            for i, notification in enumerate(notifications[:10], 1):
                formatted = formatter.format_notification({
                    'type': notification.type,
                    'title': notification.title,
                    'content': notification.content,
                    'created_at': notification.created_at
                })
                notifications_text += f"{i}. {formatted}\n\n"

            if len(notifications) > 10:
                notifications_text += f"*... и еще {len(notifications) - 10} уведомлений*\n\n"

            # Create keyboard.
            keyboard = [
                [
                    inline_keyboards.InlineKeyboardButton(
                        "✅ Прочитать все",
                        callback_data="mark_all_read"
                    ),
                    inline_keyboards.InlineKeyboardButton(
                        "🗑️ Очистить",
                        callback_data="clear_notifications"
                    )
                ],
                [
                    inline_keyboards.InlineKeyboardButton(
                        "🏠 Главное меню",
                        callback_data="main_menu"
                    )
                ]
            ]

            await update.callback_query.edit_message_text(
                notifications_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=inline_keyboards.InlineKeyboardMarkup(keyboard)
            )

    except Exception as e:
        logger.error(f"Error showing notifications: {e}")
        await update.callback_query.edit_message_text(
            "😔 Произошла ошибка при загрузке уведомлений.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )


async def mark_all_read(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mark all notifications as read."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    try:
        with db.get_session() as session:
            # Get user.
            db_user = user_crud.get_or_create(
                session,
                user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )

            # Mark all as read.
            notification_crud.mark_all_as_read(session, db_user.id)

            await query.edit_message_text(
                "✅ Все уведомления отмечены как прочитанные.",
                reply_markup=inline_keyboards.main_menu_keyboard()
            )

    except Exception as e:
        logger.error(f"Error marking notifications as read: {e}")
        await query.edit_message_text(
            "😔 Не удалось обновить уведомления.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )


async def notify_users(context: ContextTypes.DEFAULT_TYPE):
    """Check and send notifications to users."""
    try:
        with db.get_session() as session:
            # Get recent approved ads (last 10 minutes).
            recent_ads = session.query(ad_crud.Ad).filter(
                ad_crud.Ad.status == ad_crud.AdStatus.APPROVED,
                ad_crud.Ad.created_at >= datetime.now() - timedelta(minutes=10)
            ).all()

            for ad in recent_ads:
                # Get search queries that match this ad.
                matching_queries = search_query_crud.get_queries_for_notification(session, ad)

                for search_query in matching_queries:
                    # Create notification.
                    notification_crud.create_notification(
                        session,
                        user_id=search_query.user_id,
                        type="new_ad",
                        title="Новое объявление по вашему запросу",
                        content=f"Появилось новое объявление, которое соответствует вашим критериям поиска: '{ad.title}'",
                        data={"ad_id": ad.id}
                    )

                    # Update last_notified timestamp.
                    search_query.last_notified = datetime.now()
                    session.add(search_query)

                session.commit()

    except Exception as e:
        logger.error(f"Error in notify_users job: {e}")


def setup_scheduler(application):
    """Setup APScheduler for periodic tasks."""
    scheduler = AsyncIOScheduler()

    # Add notification job.
    scheduler.add_job(
        notify_users,
        trigger=IntervalTrigger(minutes=settings.NOTIFICATION_CHECK_INTERVAL),
        args=[application],
        id="notify_users",
        replace_existing=True
    )

    # Start scheduler.
    scheduler.start()
    logger.info(f"Scheduler started with {len(scheduler.get_jobs())} jobs")


def register_handlers(application):
    """Register all notification handlers."""
    application.add_handler(CallbackQueryHandler(show_notifications, pattern="^notifications$"))
    application.add_handler(CallbackQueryHandler(mark_all_read, pattern="^mark_all_read$"))

    # Setup scheduler.
    setup_scheduler(application)
