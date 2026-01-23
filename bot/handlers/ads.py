from telegram import Update, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from telegram.constants import ParseMode
import logging
from datetime import datetime
from bot.keyboards import inline_keyboards
from bot.states import AD_CREATION, AD_EDITING, END
from bot.utils import validator, formatter
from database.crud import user_crud, ad_crud
from database.models import AdStatus
from database.connection import db
from config import settings

logger = logging.getLogger(__name__)


# Ad Creation Conversation.
async def start_ad_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start ad creation conversation."""
    user = update.effective_user

    # Check if user can create more ads.
    with db.get_session() as session:
        user_ads = ad_crud.get_user_ads(session, user.id)
        if len(user_ads) >= settings.MAX_ADS_PER_USER:
            await update.callback_query.answer(
                f"Вы достигли лимита объявлений ({settings.MAX_ADS_PER_USER}). "
                "Удалите старые объявления, чтобы создать новые.",
                show_alert=True
            )
            return END

    instruction_text = (
        "📝 *Создание нового объявления*\n\n"
        "Давайте создадим ваше объявление об аренде. "
        "Ответьте на несколько вопросов:\n\n"
        "1. 📌 *Название товара* (например: 'Велосипед горный')\n"
        "2. 📋 *Описание* (опишите состояние, особенности)\n"
        "3. 💰 *Цена аренды* в рублях (например: 500)\n"
        "4. 📍 *Местоположение* (город, район, метро)\n"
        "5. 📞 *Контактная информация* (Telegram, телефон)\n\n"
        "Начнем! Введите *название товара*:"
    )

    context.user_data['ad_creation'] = {}

    if update.callback_query:
        await update.callback_query.edit_message_text(
            instruction_text,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            instruction_text,
            parse_mode=ParseMode.MARKDOWN
        )

    return AD_CREATION.TITLE


async def handle_ad_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ad title input."""
    title = update.message.text

    is_valid, result = validator.validate_title(title)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {result}\n\nПожалуйста, введите название еще раз:"
        )
        return AD_CREATION.TITLE

    context.user_data['ad_creation']['title'] = result

    await update.message.reply_text(
        "✅ Отлично! Теперь введите *описание товара*:\n\n"
        "Опишите состояние, особенности, комплектацию. "
        "Минимум 10 символов.",
        parse_mode=ParseMode.MARKDOWN
    )

    return AD_CREATION.DESCRIPTION


async def handle_ad_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ad description input."""
    description = update.message.text

    is_valid, result = validator.validate_description(description)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {result}\n\nПожалуйста, введите описание еще раз:"
        )
        return AD_CREATION.DESCRIPTION

    context.user_data['ad_creation']['description'] = result

    await update.message.reply_text(
        "✅ Отлично! Теперь введите *цену аренды* в рублях:\n\n"
        "Например: 500 (за день) или 1500.50",
        parse_mode=ParseMode.MARKDOWN
    )

    return AD_CREATION.PRICE


async def handle_ad_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ad price input."""
    price_str = update.message.text

    is_valid, result = validator.validate_price(
        price_str,
        min_price=settings.MIN_PRICE,
        max_price=settings.MAX_PRICE
    )

    if not is_valid:
        await update.message.reply_text(
            f"❌ {result}\n\nПожалуйста, введите цену еще раз:"
        )
        return AD_CREATION.PRICE

    context.user_data['ad_creation']['price'] = result

    await update.message.reply_text(
        "✅ Отлично! Теперь введите *местоположение*:\n\n"
        "Где находится товар? (город, район, ближайшее метро)",
        parse_mode=ParseMode.MARKDOWN
    )

    return AD_CREATION.LOCATION


async def handle_ad_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ad location input."""
    location = update.message.text

    is_valid, result = validator.validate_location(location)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {result}\n\nПожалуйста, введите местоположение еще раз:"
        )
        return AD_CREATION.LOCATION

    context.user_data['ad_creation']['location'] = result

    await update.message.reply_text(
        "✅ Отлично! Теперь введите *контактную информацию*:\n\n"
        "Как с вами связаться? (Telegram @username, телефон или email)\n\n"
        "Примеры:\n"
        "• @username (Telegram)\n"
        "• +7 999 123-45-67\n"
        "• email@example.com",
        parse_mode=ParseMode.MARKDOWN
    )

    return AD_CREATION.CONTACT_INFO


async def handle_ad_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ad contact info input."""
    contact_info = update.message.text

    is_valid, result = validator.validate_contact_info(contact_info)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {result}\n\nПожалуйста, введите контактную информацию еще раз:"
        )
        return AD_CREATION.CONTACT_INFO

    context.user_data['ad_creation']['contact_info'] = result

    # Show preview.
    ad_data = context.user_data['ad_creation']
    preview_text = formatter.format_ad_full(ad_data, show_contacts=True)

    keyboard = InlineKeyboardMarkup([
        [
            inline_keyboards.InlineKeyboardButton("✅ Опубликовать", callback_data="confirm_publish"),
            inline_keyboards.InlineKeyboardButton("✏️ Редактировать", callback_data="edit_ad_info")
        ],
        [
            inline_keyboards.InlineKeyboardButton("❌ Отменить", callback_data="cancel_ad_creation")
        ]
    ])

    await update.message.reply_text(
        "📋 *Предпросмотр объявления:*\n\n" + preview_text + "\n\n"
                                                            "Всё верно? Выберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )

    return AD_CREATION.CONFIRM


async def confirm_ad_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and save ad."""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_ad_creation":
        await query.edit_message_text(
            "❌ Создание объявления отменено.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )
        return END

    user = update.effective_user
    ad_data = context.user_data['ad_creation']

    try:
        with db.get_session() as session:
            # Get or create user.
            db_user = user_crud.get_or_create(
                session,
                user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )

            # Create ad.
            ad = ad_crud.create_ad(
                session,
                owner_id=db_user.id,
                title=ad_data['title'],
                description=ad_data['description'],
                price=ad_data['price'],
                location=ad_data['location'],
                contact_info=ad_data['contact_info']
            )

        success_text = (
            "✅ *Объявление успешно создано!*\n\n"
            "Ваше объявление отправлено на модерацию. "
            "Обычно это занимает несколько часов.\n\n"
            "Вы получите уведомление, когда объявление будет одобрено.\n\n"
            f"🆔 *ID объявления:* `{ad.id}`"
        )

        keyboard = inline_keyboards.main_menu_keyboard()

        await query.edit_message_text(
            success_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )

        logger.info(f"User {user.id} created ad {ad.id}")

    except Exception as e:
        logger.error(f"Error creating ad: {e}")
        await query.edit_message_text(
            "😔 Произошла ошибка при создании объявления. Пожалуйста, попробуйте позже.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )

    # Clear user data.
    if 'ad_creation' in context.user_data:
        del context.user_data['ad_creation']

    return END


# My Ads Management.
async def show_my_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's ads."""
    user = update.effective_user

    try:
        with db.get_session() as session:
            # Get or create user.
            db_user = user_crud.get_or_create(
                session,
                user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )

            # Get user's ads.
            ads = ad_crud.get_user_ads(session, db_user.id)

            if not ads:
                await update.callback_query.edit_message_text(
                    "📭 *У вас пока нет объявлений*\n\n"
                    "Создайте первое объявление об аренде!",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=inline_keyboards.main_menu_keyboard()
                )
                return

            # Prepare ads list.
            ads_text = "📋 *Ваши объявления:*\n\n"

            for i, ad in enumerate(ads[:10], 1):
                status_emoji = {
                    AdStatus.DRAFT: '📝',
                    AdStatus.PENDING: '⏳',
                    AdStatus.APPROVED: '✅',
                    AdStatus.REJECTED: '❌',
                    AdStatus.RENTED: '🎉',
                    AdStatus.ARCHIVED: '📁'
                }.get(ad.status, '❓')

                ads_text += (
                    f"{i}. {status_emoji} *{formatter.escape_markdown(ad.title)}*\n"
                    f"   💰 {formatter.format_price(ad.price)}\n"
                    f"   📍 {formatter.escape_markdown(ad.location)}\n"
                    f"   🆔 `{ad.id}` • {ad.status.value}\n\n"
                )

            if len(ads) > 10:
                ads_text += f"*... и еще {len(ads) - 10} объявлений*\n\n"

            ads_text += "Выберите объявление для управления:"

            # Create keyboard with ads.
            keyboard = []
            for ad in ads[:5]:  # Show first 5 ads.
                keyboard.append([
                    inline_keyboards.InlineKeyboardButton(
                        f"{ad.title[:20]}... ({ad.status.value})",
                        callback_data=f"manage_ad_{ad.id}"
                    )
                ])

            keyboard.append([
                inline_keyboards.InlineKeyboardButton("📝 Создать новое", callback_data="create_ad"),
                inline_keyboards.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
            ])

            if len(ads) > 5:
                keyboard.append([
                    inline_keyboards.InlineKeyboardButton("➡️ Следующие", callback_data="my_ads_page_2")
                ])

            await update.callback_query.edit_message_text(
                ads_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    except Exception as e:
        logger.error(f"Error showing user ads: {e}")
        await update.callback_query.edit_message_text(
            "😔 Произошла ошибка при загрузке объявлений.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )


async def manage_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage specific ad."""
    query = update.callback_query
    await query.answer()

    ad_id = int(query.data.split('_')[2])
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

            # Get ad.
            ad = ad_crud.get_ad(session, ad_id)

            if not ad or ad.owner_id != db_user.id:
                await query.edit_message_text(
                    "❌ Объявление не найдено или у вас нет прав для управления.",
                    reply_markup=inline_keyboards.main_menu_keyboard()
                )
                return

            # Format ad info.
            ad_info = formatter.format_ad_full({
                'id': ad.id,
                'title': ad.title,
                'description': ad.description,
                'price': ad.price,
                'location': ad.location,
                'contact_info': ad.contact_info,
                'created_at': ad.created_at,
                'status': ad.status.value
            }, show_contacts=True)

            # Add stats if available.
            stats_text = "\n\n📊 *Статистика:*\n"

            # Get message count.
            message_count = len(ad.messages) if hasattr(ad, 'messages') else 0
            stats_text += f"• 💬 Сообщений: {message_count}\n"

            # Get feedback stats.
            if hasattr(ad, 'feedbacks'):
                ratings = [f.rating for f in ad.feedbacks if f.rating]
                if ratings:
                    avg_rating = sum(ratings) / len(ratings)
                    stats_text += f"• ⭐ Рейтинг: {avg_rating:.1f}/5 ({len(ratings)} отзывов)\n"

            status_info = {
                AdStatus.DRAFT: "✏️ *Черновик* — объявление еще не отправлено на модерацию",
                AdStatus.PENDING: "⏳ *На модерации* — ожидает проверки администратором",
                AdStatus.APPROVED: "✅ *Одобрено* — объявление видно всем в поиске",
                AdStatus.REJECTED: f"❌ *Отклонено* — {ad.rejection_reason or 'Причина не указана'}",
                AdStatus.RENTED: "🎉 *Сдано* — товар сейчас в аренде",
                AdStatus.ARCHIVED: "📁 *В архиве* — объявление скрыто"
            }.get(ad.status, "❓ *Неизвестный статус*")

            full_text = f"📋 *Управление объявлением*\n\n{ad_info}\n{stats_text}\n\n{status_info}"

            # Create management keyboard.
            keyboard = inline_keyboards.ad_status_keyboard(ad.id)

            await query.edit_message_text(
                full_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Error managing ad: {e}")
        await query.edit_message_text(
            "😔 Произошла ошибка при загрузке объявления.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )


async def edit_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start editing ad."""
    query = update.callback_query
    await query.answer()

    ad_id = int(query.data.split('_')[2])
    user = update.effective_user

    # Store ad_id in context for editing.
    context.user_data['editing_ad_id'] = ad_id

    # Show edit options.
    edit_text = (
        "✏️ *Редактирование объявления*\n\n"
        "Что вы хотите изменить?\n\n"
        "1. 📌 Название товара\n"
        "2. 📋 Описание\n"
        "3. 💰 Цену аренды\n"
        "4. 📍 Местоположение\n"
        "5. 📞 Контактную информацию\n"
        "6. 🏷️ Категорию\n"
        "7. 📊 Статус (например, сдано в аренду)"
    )

    keyboard = InlineKeyboardMarkup([
        [
            inline_keyboards.InlineKeyboardButton("📌 Название", callback_data=f"edit_field_title_{ad_id}"),
            inline_keyboards.InlineKeyboardButton("📋 Описание", callback_data=f"edit_field_description_{ad_id}")
        ],
        [
            inline_keyboards.InlineKeyboardButton("💰 Цена", callback_data=f"edit_field_price_{ad_id}"),
            inline_keyboards.InlineKeyboardButton("📍 Местоположение", callback_data=f"edit_field_location_{ad_id}")
        ],
        [
            inline_keyboards.InlineKeyboardButton("📞 Контакты", callback_data=f"edit_field_contacts_{ad_id}"),
            inline_keyboards.InlineKeyboardButton("🏷️ Категория", callback_data=f"edit_field_category_{ad_id}")
        ],
        [
            inline_keyboards.InlineKeyboardButton("📊 Статус", callback_data=f"edit_field_status_{ad_id}"),
            inline_keyboards.InlineKeyboardButton("◀️ Назад", callback_data=f"manage_ad_{ad_id}")
        ]
    ])

    await query.edit_message_text(
        edit_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )


async def delete_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm ad deletion."""
    query = update.callback_query
    await query.answer()

    ad_id = int(query.data.split('_')[2])

    confirm_text = (
        "⚠️ *Подтверждение удаления*\n\n"
        "Вы уверены, что хотите удалить это объявление?\n\n"
        "Это действие нельзя отменить. Все данные объявления, "
        "сообщения и отзывы будут удалены."
    )

    keyboard = inline_keyboards.confirmation_keyboard("delete_ad", ad_id)

    await query.edit_message_text(
        confirm_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )


async def confirm_delete_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and delete ad."""
    query = update.callback_query
    await query.answer()

    ad_id = int(query.data.split('_')[2])
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

            # Delete ad.
            success = ad_crud.delete_ad(session, ad_id, db_user.id)

            if success:
                await query.edit_message_text(
                    "✅ Объявление успешно удалено.",
                    reply_markup=inline_keyboards.main_menu_keyboard()
                )
                logger.info(f"User {user.id} deleted ad {ad_id}")
            else:
                await query.edit_message_text(
                    "❌ Не удалось удалить объявление. Возможно, оно уже удалено.",
                    reply_markup=inline_keyboards.main_menu_keyboard()
                )

    except Exception as e:
        logger.error(f"Error deleting ad: {e}")
        await query.edit_message_text(
            "😔 Произошла ошибка при удалении объявления.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )


# Register handlers.
def register_handlers(application):
    """Register all ad handlers."""

    # Ad creation conversation.
    ad_creation_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_ad_creation, pattern="^create_ad$"),
            CallbackQueryHandler(start_ad_creation, pattern="^confirm_publish$")
        ],
        states={
            AD_CREATION.TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ad_title)
            ],
            AD_CREATION.DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ad_description)
            ],
            AD_CREATION.PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ad_price)
            ],
            AD_CREATION.LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ad_location)
            ],
            AD_CREATION.CONTACT_INFO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ad_contact_info)
            ],
            AD_CREATION.CONFIRM: [
                CallbackQueryHandler(confirm_ad_creation, pattern="^(confirm_publish|cancel_ad_creation)$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            CallbackQueryHandler(cancel_command, pattern="^cancel_ad_creation$")
        ]
    )

    application.add_handler(ad_creation_conv)

    # My ads management.
    application.add_handler(CallbackQueryHandler(show_my_ads, pattern="^my_ads$"))
    application.add_handler(CallbackQueryHandler(manage_ad, pattern="^manage_ad_"))
    application.add_handler(CallbackQueryHandler(edit_ad, pattern="^edit_ad_"))
    application.add_handler(CallbackQueryHandler(delete_ad, pattern="^delete_ad_"))
    application.add_handler(CallbackQueryHandler(confirm_delete_ad, pattern="^confirm_delete_ad_"))

    # Ad editing (simplified for now).
    async def handle_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        # This would be expanded with actual editing logic.
        await query.edit_message_text(
            "✏️ Редактирование будет доступно в следующем обновлении.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )

    application.add_handler(CallbackQueryHandler(handle_edit_field, pattern="^edit_field_"))
