from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from telegram.constants import ParseMode
import logging
from datetime import datetime

from bot.keyboards import inline_keyboards
from bot.states import FEEDBACK, END
from bot.utils import formatter
from database.crud import (
    user_crud, ad_crud, feedback_crud,
    notification_crud
)
from database.connection import db

logger = logging.getLogger(__name__)


async def start_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start feedback interface."""
    feedback_text = (
        "⭐ *Система отзывов*\n\n"
        "Здесь вы можете:\n"
        "• ⭐ Оценить арендованную вещь\n"
        "• 🤖 Оставить отзыв о боте\n"
        "• 📝 Посмотреть свои отзывы\n"
        "• 📊 Посмотреть общую статистику\n\n"
        "Отзывы помогают улучшить сервис и "
        "сделать аренду безопаснее для всех!"
    )

    keyboard = inline_keyboards.feedback_keyboard()

    if update.callback_query:
        await update.callback_query.edit_message_text(
            feedback_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            feedback_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )


async def rate_ad_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start rating an ad."""
    query = update.callback_query
    await query.answer()

    # Check if we have ad_id in callback data.
    if query.data.startswith("rate_ad_"):
        ad_id = int(query.data.split('_')[2])
        context.user_data['feedback_ad_id'] = ad_id

        try:
            with db.get_session() as session:
                ad = ad_crud.get_ad(session, ad_id)
                if ad:
                    context.user_data['feedback_ad_title'] = ad.title

                    rating_text = (
                        f"⭐ *Оценка объявления*\n\n"
                        f"Вы оцениваете: *{formatter.escape_markdown(ad.title)}*\n\n"
                        f"Пожалуйста, выберите оценку от 1 до 5 звезд:\n\n"
                        f"1 ⭐ — Ужасно\n"
                        f"2 ⭐ — Плохо\n"
                        f"3 ⭐ — Нормально\n"
                        f"4 ⭐ — Хорошо\n"
                        f"5 ⭐ — Отлично"
                    )

                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("1 ⭐", callback_data="feedback_rate_1"),
                            InlineKeyboardButton("2 ⭐", callback_data="feedback_rate_2"),
                            InlineKeyboardButton("3 ⭐", callback_data="feedback_rate_3"),
                            InlineKeyboardButton("4 ⭐", callback_data="feedback_rate_4"),
                            InlineKeyboardButton("5 ⭐", callback_data="feedback_rate_5")
                        ],
                        [
                            InlineKeyboardButton("◀️ Назад", callback_data="feedback"),
                            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
                        ]
                    ])

                    await query.edit_message_text(
                        rating_text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=keyboard
                    )
                    return
        except Exception as e:
            logger.error(f"Error getting ad for feedback: {e}")

    # General ad feedback.
    context.user_data['feedback_type'] = 'ad'

    rating_text = (
        "⭐ *Оценка объявления*\n\n"
        "Пожалуйста, выберите объявление для оценки или "
        "введите его ID вручную.\n\n"
        "Введите ID объявления (число):"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Мои объявления", callback_data="my_ads_for_feedback")],
        [InlineKeyboardButton("◀️ Назад", callback_data="feedback")]
    ])

    await query.edit_message_text(
        rating_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )

    return FEEDBACK.RATING


async def handle_ad_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ad ID input for feedback."""
    try:
        ad_id = int(update.message.text)
        user = update.effective_user

        with db.get_session() as session:
            # Get user.
            db_user = user_crud.get_or_create(
                session,
                user.id,
                username=user.username,
                first_name=user.first_name
            )

            # Check if ad exists and user has permission to rate it.
            ad = ad_crud.get_ad(session, ad_id)

            if not ad:
                await update.message.reply_text(
                    "❌ Объявление с таким ID не найдено.\n"
                    "Пожалуйста, введите правильный ID объявления:"
                )
                return FEEDBACK.RATING

            # Check if user already left feedback for this ad.
            existing_feedback = session.query(feedback_crud.Feedback).filter(
                feedback_crud.Feedback.user_id == db_user.id,
                feedback_crud.Feedback.ad_id == ad_id
            ).first()

            if existing_feedback:
                await update.message.reply_text(
                    "❌ Вы уже оставляли отзыв для этого объявления.\n"
                    "Пожалуйста, введите ID другого объявления:"
                )
                return FEEDBACK.RATING

            # Store ad info in context.
            context.user_data['feedback_ad_id'] = ad_id
            context.user_data['feedback_ad_title'] = ad.title

            # Ask for rating.
            await update.message.reply_text(
                f"✅ Объявление найдено: *{formatter.escape_markdown(ad.title)}*\n\n"
                "Пожалуйста, выберите оценку (от 1 до 5):\n\n"
                "1 ⭐ — Ужасно\n"
                "2 ⭐ — Плохо\n"
                "3 ⭐ — Нормально\n"
                "4 ⭐ — Хорошо\n"
                "5 ⭐ — Отлично\n\n"
                "Отправьте число от 1 до 5:",
                parse_mode=ParseMode.MARKDOWN
            )

            return FEEDBACK.COMMENT

    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. Пожалуйста, введите число:"
        )
        return FEEDBACK.RATING
    except Exception as e:
        logger.error(f"Error handling ad ID input: {e}")
        await update.message.reply_text(
            "😔 Произошла ошибка. Пожалуйста, попробуйте еще раз:"
        )
        return FEEDBACK.RATING


async def handle_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle rating selection."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        rating = int(query.data.split('_')[2])
        context.user_data['feedback_rating'] = rating

        # If we have ad_id from callback, proceed to comment.
        if 'feedback_ad_id' in context.user_data:
            ad_title = context.user_data.get('feedback_ad_title', 'это объявление')

            await query.edit_message_text(
                f"✅ Вы выбрали оценку: {rating} ⭐\n\n"
                f"Теперь вы можете оставить комментарий к объявлению '{ad_title}'.\n\n"
                "💬 *Напишите ваш комментарий:*\n"
                "(или отправьте /skip чтобы пропустить)",
                parse_mode=ParseMode.MARKDOWN
            )

            return FEEDBACK.COMMENT
    else:
        try:
            rating = int(update.message.text)
            if rating < 1 or rating > 5:
                await update.message.reply_text(
                    "❌ Оценка должна быть от 1 до 5. Пожалуйста, введите число от 1 до 5:"
                )
                return FEEDBACK.COMMENT

            context.user_data['feedback_rating'] = rating

            if 'feedback_ad_id' in context.user_data:
                ad_title = context.user_data.get('feedback_ad_title', 'это объявление')

                await update.message.reply_text(
                    f"✅ Вы выбрали оценку: {rating} ⭐\n\n"
                    f"Теперь вы можете оставить комментарий к объявлению '{ad_title}'.\n\n"
                    "💬 *Напишите ваш комментарий:*\n"
                    "(или отправьте /skip чтобы пропустить)",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    f"✅ Вы выбрали оценку: {rating} ⭐\n\n"
                    "Теперь вы можете оставить комментарий о боте.\n\n"
                    "💬 *Напишите ваш комментарий:*\n"
                    "(или отправьте /skip чтобы пропустить)",
                    parse_mode=ParseMode.MARKDOWN
                )

            return FEEDBACK.COMMENT

        except ValueError:
            await update.message.reply_text(
                "❌ Пожалуйста, введите число от 1 до 5:"
            )
            return FEEDBACK.COMMENT


async def handle_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle feedback comment"""
    if update.message.text == '/skip':
        comment = None
    else:
        comment = update.message.text[:500]  # Limit comment length

    context.user_data['feedback_comment'] = comment

    # Determine feedback type.
    feedback_type = context.user_data.get('feedback_type', 'ad')

    # Prepare confirmation message.
    rating = context.user_data['feedback_rating']
    stars = '⭐' * rating + '☆' * (5 - rating)

    if feedback_type == 'ad' and 'feedback_ad_title' in context.user_data:
        ad_title = context.user_data['feedback_ad_title']
        confirm_text = (
            f"📋 *Подтверждение отзыва*\n\n"
            f"🏷️ *Объявление:* {formatter.escape_markdown(ad_title)}\n"
            f"⭐ *Оценка:* {stars}\n"
        )
    else:
        confirm_text = (
            f"📋 *Подтверждение отзыва*\n\n"
            f"🤖 *Тип:* Отзыв о боте\n"
            f"⭐ *Оценка:* {stars}\n"
        )

    if comment:
        confirm_text += f"💬 *Комментарий:* {formatter.escape_markdown(comment[:100])}"
        if len(comment) > 100:
            confirm_text += "..."
    else:
        confirm_text += "💬 *Комментарий:* Без комментария"

    confirm_text += "\n\nВсё верно?"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Да, отправить", callback_data="confirm_feedback"),
            InlineKeyboardButton("✏️ Изменить", callback_data="edit_feedback")
        ],
        [
            InlineKeyboardButton("❌ Отменить", callback_data="cancel_feedback")
        ]
    ])

    await update.message.reply_text(
        confirm_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )

    return FEEDBACK.CONFIRM


async def confirm_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and save feedback."""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_feedback":
        await query.edit_message_text(
            "❌ Создание отзыва отменено.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )
        return END

    user = update.effective_user
    rating = context.user_data['feedback_rating']
    comment = context.user_data.get('feedback_comment')
    feedback_type = context.user_data.get('feedback_type', 'ad')

    try:
        with db.get_session() as session:
            # Get user.
            db_user = user_crud.get_or_create(
                session,
                user.id,
                username=user.username,
                first_name=user.first_name
            )

            ad_id = None
            if feedback_type == 'ad' and 'feedback_ad_id' in context.user_data:
                ad_id = context.user_data['feedback_ad_id']

            # Create feedback.
            feedback = feedback_crud.create_feedback(
                session,
                user_id=db_user.id,
                rating=rating,
                comment=comment,
                ad_id=ad_id,
                feedback_type=feedback_type
            )

            # Send notification to ad owner if applicable.
            if ad_id:
                ad = ad_crud.get_ad(session, ad_id)
                if ad and ad.owner_id != db_user.id:
                    notification_crud.create_notification(
                        session,
                        user_id=ad.owner_id,
                        type="new_feedback",
                        title="Новый отзыв",
                        content=f"Ваше объявление '{ad.title}' получило новый отзыв: {rating} ⭐",
                        data={"ad_id": ad.id, "feedback_id": feedback.id}
                    )

            success_text = "✅ *Спасибо за ваш отзыв!*\n\n"

            if feedback_type == 'ad':
                ad_title = context.user_data.get('feedback_ad_title', 'объявление')
                success_text += f"Ваш отзыв на '{ad_title}' успешно сохранен.\n"
            else:
                success_text += "Ваш отзыв о боте успешно сохранен.\n"

            success_text += "Он поможет другим пользователям сделать правильный выбор!"

            # Clear user data.
            for key in ['feedback_rating', 'feedback_comment', 'feedback_type',
                        'feedback_ad_id', 'feedback_ad_title']:
                if key in context.user_data:
                    del context.user_data[key]

            await query.edit_message_text(
                success_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=inline_keyboards.main_menu_keyboard()
            )

            logger.info(f"User {user.id} submitted {feedback_type} feedback with rating {rating}")

    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        await query.edit_message_text(
            "😔 Произошла ошибка при сохранении отзыва.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )

    return END


async def show_my_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's feedback."""
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
                first_name=user.first_name
            )

            # Get user's feedback.
            feedbacks = session.query(feedback_crud.Feedback).filter(
                feedback_crud.Feedback.user_id == db_user.id
            ).order_by(
                feedback_crud.Feedback.created_at.desc()
            ).limit(10).all()

            if not feedbacks:
                await query.edit_message_text(
                    "📭 *У вас пока нет отзывов*\n\n"
                    "Оставьте первый отзыв на объявление или о боте!",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=inline_keyboards.feedback_keyboard()
                )
                return

            feedback_text = "⭐ *Ваши отзывы*\n\n"

            for i, fb in enumerate(feedbacks, 1):
                stars = '⭐' * fb.rating + '☆' * (5 - fb.rating)

                if fb.type == 'ad' and fb.ad:
                    item_name = f"Объявление: {fb.ad.title}"
                else:
                    item_name = "Бот"

                time_ago = formatter.time_ago(fb.created_at)

                feedback_text += f"{i}. {stars} *{item_name}*\n"
                if fb.comment:
                    comment_preview = fb.comment[:50]
                    if len(fb.comment) > 50:
                        comment_preview += "..."
                    feedback_text += f"   💬 {comment_preview}\n"
                feedback_text += f"   🕐 {time_ago}\n\n"

            if len(feedbacks) == 10:
                feedback_text += "*... и другие отзывы*\n\n"

            feedback_text += "Всего отзывов: " + str(len(feedbacks))

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ Оставить новый отзыв", callback_data="feedback_ad")],
                [InlineKeyboardButton("◀️ Назад", callback_data="feedback")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ])

            await query.edit_message_text(
                feedback_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Error showing user feedback: {e}")
        await query.edit_message_text(
            "😔 Произошла ошибка при загрузке отзывов.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )


async def show_feedback_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show feedback statistics."""
    query = update.callback_query
    await query.answer()

    try:
        with db.get_session() as session:
            from sqlalchemy import func

            # Bot feedback stats.
            bot_feedbacks = session.query(
                func.avg(feedback_crud.Feedback.rating).label('avg_rating'),
                func.count(feedback_crud.Feedback.id).label('total')
            ).filter(
                feedback_crud.Feedback.type == 'bot'
            ).first()

            # Ad feedback stats.
            ad_feedbacks = session.query(
                func.avg(feedback_crud.Feedback.rating).label('avg_rating'),
                func.count(feedback_crud.Feedback.id).label('total')
            ).filter(
                feedback_crud.Feedback.type == 'ad'
            ).first()

            # Recent feedback.
            recent_feedbacks = session.query(feedback_crud.Feedback).join(
                user_crud.User
            ).order_by(
                feedback_crud.Feedback.created_at.desc()
            ).limit(3).all()

            stats_text = "📊 *Статистика отзывов*\n\n"

            # Bot stats.
            if bot_feedbacks and bot_feedbacks.total > 0:
                avg_bot = bot_feedbacks.avg_rating or 0
                stars = '⭐' * int(round(avg_bot)) + '☆' * (5 - int(round(avg_bot)))
                stats_text += f"🤖 *Бот:* {stars} ({avg_bot:.1f}/5)\n"
                stats_text += f"   📝 Всего отзывов: {bot_feedbacks.total}\n\n"
            else:
                stats_text += "🤖 *Бот:* Нет отзывов\n\n"

            # Ad stats.
            if ad_feedbacks and ad_feedbacks.total > 0:
                avg_ad = ad_feedbacks.avg_rating or 0
                stars = '⭐' * int(round(avg_ad)) + '☆' * (5 - int(round(avg_ad)))
                stats_text += f"🏷️ *Объявления:* {stars} ({avg_ad:.1f}/5)\n"
                stats_text += f"   📝 Всего отзывов: {ad_feedbacks.total}\n\n"
            else:
                stats_text += "🏷️ *Объявления:* Нет отзывов\n\n"

            # Recent feedback.
            if recent_feedbacks:
                stats_text += "🆕 *Последние отзывы:*\n"
                for fb in recent_feedbacks:
                    username = fb.user.username or fb.user.first_name or f"Пользователь {fb.user.id}"
                    stars = '⭐' * fb.rating + '☆' * (5 - fb.rating)

                    if fb.type == 'ad' and fb.ad:
                        item = f"{fb.ad.title[:20]}..."
                    else:
                        item = "Бот"

                    stats_text += f"• {stars} от @{username} ({item})\n"

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Обновить", callback_data="feedback_stats")],
                [InlineKeyboardButton("◀️ Назад", callback_data="feedback")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ])

            await query.edit_message_text(
                stats_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Error showing feedback stats: {e}")
        await query.edit_message_text(
            "😔 Произошла ошибка при загрузке статистики.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )


async def bot_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start bot feedback process."""
    query = update.callback_query
    await query.answer()

    context.user_data['feedback_type'] = 'bot'

    rating_text = (
        "🤖 *Отзыв о боте*\n\n"
        "Пожалуйста, оцените работу бота Rent from Anton:\n\n"
        "1 ⭐ — Ужасно\n"
        "2 ⭐ — Плохо\n"
        "3 ⭐ — Нормально\n"
        "4 ⭐ — Хорошо\n"
        "5 ⭐ — Отлично\n\n"
        "Выберите оценку:"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1 ⭐", callback_data="feedback_rate_1"),
            InlineKeyboardButton("2 ⭐", callback_data="feedback_rate_2"),
            InlineKeyboardButton("3 ⭐", callback_data="feedback_rate_3"),
            InlineKeyboardButton("4 ⭐", callback_data="feedback_rate_4"),
            InlineKeyboardButton("5 ⭐", callback_data="feedback_rate_5")
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="feedback")
        ]
    ])

    await query.edit_message_text(
        rating_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )

    return FEEDBACK.COMMENT


# Register handlers.
def register_handlers(application):
    """Register all feedback handlers."""

    # Feedback conversation.
    feedback_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(rate_ad_feedback, pattern="^feedback_ad$"),
            CallbackQueryHandler(bot_feedback, pattern="^feedback_bot$"),
            CallbackQueryHandler(handle_rating, pattern="^feedback_rate_")
        ],
        states={
            FEEDBACK.RATING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ad_id_input),
                CallbackQueryHandler(handle_rating, pattern="^feedback_rate_")
            ],
            FEEDBACK.COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_comment),
                CallbackQueryHandler(handle_rating, pattern="^feedback_rate_")
            ],
            FEEDBACK.CONFIRM: [
                CallbackQueryHandler(confirm_feedback, pattern="^(confirm_feedback|edit_feedback|cancel_feedback)$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", lambda u, c: END),
            CallbackQueryHandler(lambda u, c: END, pattern="^cancel_feedback$")
        ]
    )

    application.add_handler(feedback_conv)

    # Other feedback handlers.
    application.add_handler(CallbackQueryHandler(start_feedback, pattern="^feedback$"))
    application.add_handler(CallbackQueryHandler(show_my_feedback, pattern="^my_feedback$"))
    application.add_handler(CallbackQueryHandler(show_feedback_stats, pattern="^feedback_stats$"))

    # Direct ad rating.
    application.add_handler(CallbackQueryHandler(rate_ad_feedback, pattern="^rate_ad_"))
