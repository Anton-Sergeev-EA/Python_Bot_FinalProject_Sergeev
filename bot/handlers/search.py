from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.constants import ParseMode
import logging
from bot.keyboards import inline_keyboards
from bot.utils import formatter, validator
from database.crud import ad_crud, search_query_crud, user_crud
from database.connection import db

logger = logging.getLogger(__name__)


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start search interface."""
    # Initialize search filters.
    context.user_data['search_filters'] = {
        'keywords': None,
        'location': None,
        'min_price': None,
        'max_price': None,
        'category_id': None
    }

    search_text = (
        "🔍 *Поиск объявлений*\n\n"
        "Используйте фильтры для поиска нужных товаров:\n\n"
        "• 🔤 *Ключевые слова* — поиск по названию и описанию\n"
        "• 📍 *Местоположение* — поиск по городу/району\n"
        "• 💰 *Цена* — диапазон цен\n"
        "• 🏷️ *Категория* — фильтр по категориям\n\n"
        "Вы можете сохранить поиск для получения уведомлений."
    )

    keyboard = inline_keyboards.search_filters_keyboard()

    await update.callback_query.edit_message_text(
        search_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )


async def execute_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute search with current filters."""
    query = update.callback_query
    await query.answer()

    filters = context.user_data.get('search_filters', {})

    try:
        with db.get_session() as session:
            # Search ads.
            ads = ad_crud.search_ads(
                session,
                keywords=filters.get('keywords'),
                location=filters.get('location'),
                min_price=filters.get('min_price'),
                max_price=filters.get('max_price'),
                category_id=filters.get('category_id'),
                limit=20
            )

            if not ads:
                await query.edit_message_text(
                    "😔 *Ничего не найдено*\n\n"
                    "Попробуйте изменить параметры поиска.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=inline_keyboards.search_filters_keyboard()
                )
                return

            # Store ads in context for pagination.
            context.user_data['search_results'] = [
                {
                    'id': ad.id,
                    'title': ad.title,
                    'description': ad.description,
                    'price': ad.price,
                    'location': ad.location,
                    'created_at': ad.created_at,
                    'owner_id': ad.owner_id
                }
                for ad in ads
            ]
            context.user_data['current_search_page'] = 1

            # Show first result.
            await show_search_results(update, context)

    except Exception as e:
        logger.error(f"Error executing search: {e}")
        await query.edit_message_text(
            "😔 Произошла ошибка при поиске.",
            reply_markup=inline_keyboards.main_menu_keyboard()
        )


async def show_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show search results with pagination."""
    query = update.callback_query
    if query:
        await query.answer()

    results = context.user_data.get('search_results', [])
    current_page = context.user_data.get('current_search_page', 1)

    if not results:
        return

    items_per_page = 5
    total_pages = (len(results) + items_per_page - 1) // items_per_page
    start_idx = (current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page

    page_results = results[start_idx:end_idx]

    # Build results text.
    results_text = f"🔍 *Результаты поиска* (стр. {current_page}/{total_pages})\n\n"

    for i, ad in enumerate(page_results, start_idx + 1):
        preview = formatter.format_ad_preview(ad)
        results_text += f"{i}. {preview}\n"

    # Create pagination keyboard.
    keyboard = inline_keyboards.pagination_keyboard(
        current_page,
        total_pages,
        "search",
        None
    )

    # Add action buttons for each ad.
    action_buttons = []
    for i, ad in enumerate(page_results):
        idx = start_idx + i + 1
        action_buttons.append([
            inline_keyboards.InlineKeyboardButton(
                f"📄 {idx}. {ad['title'][:15]}...",
                callback_data=f"view_ad_{ad['id']}"
            )
        ])

    if action_buttons:
        keyboard = InlineKeyboardMarkup(
            action_buttons + keyboard.inline_keyboard
        )

    if query:
        await query.edit_message_text(
            results_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            results_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )


async def save_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save search query for notifications."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    filters = context.user_data.get('search_filters', {})

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

            # Save search query.
            search_query = search_query_crud.save_search_query(
                session,
                db_user.id,
                keywords=filters.get('keywords'),
                location=filters.get('location'),
                min_price=filters.get('min_price'),
                max_price=filters.get('max_price'),
                category_id=filters.get('category_id')
            )

            await query.edit_message_text(
                "✅ *Поиск сохранен!*\n\n"
                "Вы будете получать уведомления, когда появятся новые объявления, "
                "соответствующие вашим критериям.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=inline_keyboards.search_filters_keyboard()
            )

    except Exception as e:
        logger.error(f"Error saving search query: {e}")
        await query.edit_message_text(
            "😔 Не удалось сохранить поиск.",
            reply_markup=inline_keyboards.search_filters_keyboard()
        )


def register_handlers(application):
    """Register all search handlers."""
    application.add_handler(CallbackQueryHandler(start_search, pattern="^search$"))
    application.add_handler(CallbackQueryHandler(execute_search, pattern="^execute_search$"))
    application.add_handler(CallbackQueryHandler(save_search_query, pattern="^save_search$"))
    application.add_handler(CallbackQueryHandler(show_search_results, pattern="^search_page_"))
