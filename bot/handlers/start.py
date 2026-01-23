from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode
import logging

try:
    from ..keyboards import inline_keyboards
except ImportError:
    try:
        from bot.keyboards import inline_keyboards
    except ImportError:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup


        class MinimalKeyboards:
            @staticmethod
            def main_menu_keyboard():
                return InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 Поиск", callback_data="search")],
                    [InlineKeyboardButton("📝 Создать", callback_data="create_ad")]
                ])


        inline_keyboards = MinimalKeyboards()

from database.crud import user_crud
from database.connection import db
from config import settings

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    try:
        user = update.effective_user
        message = update.message

        # Get or create user in database.
        with db.get_session() as session:
            db_user = user_crud.get_or_create(
                session,
                user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )

        welcome_text = (
            f"👋 *Добро пожаловать, {user.first_name}!*\n\n"
            "🤖 *Rent from Anton* — бот для аренды вещей\n\n"
            "✨ *Что вы можете сделать:*\n"
            "• 📝 Разместить объявление об аренде\n"
            "• 🔍 Найти нужные вещи поблизости\n"
            "• 💬 Связаться с владельцами напрямую\n"
            "• ⭐ Оставлять и читать отзывы\n"
            "• 🔔 Получать уведомления о новых предложениях\n\n"
            "📱 *Используйте меню ниже для навигации*"
        )

        # Check if user is admin.
        is_admin = user.id in settings.ADMIN_IDS

        keyboard = inline_keyboards.main_menu_keyboard()
        if is_admin:
            # Add admin button for admins.
            keyboard = InlineKeyboardMarkup(
                keyboard.inline_keyboard +
                [[InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")]]
            )

        if message:
            await message.reply_text(
                welcome_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                welcome_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )

        logger.info(f"User {user.id} started the bot")

    except Exception as e:
        logger.error(f"Error in start command: {e}")
        if update.message:
            await update.message.reply_text(
                "😔 Произошла ошибка при запуске бота. Пожалуйста, попробуйте позже."
            )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = (
        "❓ *Помощь и поддержка*\n\n"
        "📚 *Основные команды:*\n"
        "• /start — Перезапустить бота\n"
        "• /help — Показать это сообщение\n"
        "• /menu — Показать главное меню\n"
        "• /cancel — Отменить текущее действие\n\n"
        "🔧 *Как пользоваться:*\n"
        "1. 📝 *Создать объявление:*\n"
        "   • Нажмите 'Создать объявление'\n"
        "   • Заполните все поля\n"
        "   • Объявление отправится на модерацию\n"
        "   • После одобрения оно появится в поиске\n\n"
        "2. 🔍 *Искать объявления:*\n"
        "   • Нажмите 'Поиск объявлений'\n"
        "   • Используйте фильтры для уточнения\n"
        "   • Сохраните поиск для уведомлений\n\n"
        "3. 💬 *Общаться с владельцами:*\n"
        "   • Нажмите 'Связаться' в объявлении\n"
        "   • Напишите сообщение владельцу\n"
        "   • Все сообщения хранятся в 'Мои сообщения'\n\n"
        "4. ⭐ *Оставлять отзывы:*\n"
        "   • Оцените объявление после аренды\n"
        "   • Оставьте отзыв о боте\n"
        "   • Читайте отзывы других пользователей\n\n"
        "🛡️ *Безопасность:*\n"
        "• Не передавайте пароли и платежные данные\n"
        "• Встречайтесь в общественных местах\n"
        "• Проверяйте вещи перед арендой\n"
        "• Сообщайте о подозрительных объявлениях\n\n"
        "📞 *Поддержка:*\n"
        "Если у вас возникли проблемы или вопросы, "
        "обращайтесь к администратору через кнопку 'Помощь' в меню."
    )

    keyboard = inline_keyboards.main_menu_keyboard()

    if update.message:
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu command."""
    await start_command(update, context)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command."""
    # Clear user data.
    if 'user_data' in context:
        for key in list(context.user_data.keys()):
            if not key.startswith('_'):
                del context.user_data[key]

    cancel_text = "❌ Текущее действие отменено."

    keyboard = inline_keyboards.main_menu_keyboard()

    if update.message:
        await update.message.reply_text(
            cancel_text,
            reply_markup=keyboard
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            cancel_text,
            reply_markup=keyboard
        )

    return -1  # End conversation.


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu callback."""
    await start_command(update, context)


async def handle_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin panel callback."""
    user = update.effective_user

    if user.id not in settings.ADMIN_IDS:
        await update.callback_query.answer("У вас нет доступа к админ-панели", show_alert=True)
        return

    admin_text = (
        "👑 *Админ-панель*\n\n"
        "Здесь вы можете управлять системой:\n\n"
        "• 👁️ *Модерация* — просмотр и проверка объявлений\n"
        "• 📊 *Статистика* — общая статистика системы\n"
        "• 👥 *Пользователи* — управление пользователями\n"
        "• 📝 *Объявления* — управление всеми объявлениями\n"
        "• ⭐ *Отзывы* — просмотр отзывов\n"
        "• ⚙️ *Настройки* — настройки системы\n"
    )

    keyboard = inline_keyboards.admin_keyboard()

    await update.callback_query.edit_message_text(
        admin_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )


# Register handlers
def register_handlers(application):
    """Register all start handlers."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("cancel", cancel_command))

    application.add_handler(CallbackQueryHandler(handle_main_menu, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(handle_admin_panel, pattern="^admin_panel$"))
