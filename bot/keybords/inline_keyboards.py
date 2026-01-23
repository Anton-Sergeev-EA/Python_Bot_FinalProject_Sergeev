from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🔍 Поиск объявлений", callback_data="search"),
            InlineKeyboardButton("📝 Создать объявление", callback_data="create_ad")
        ],
        [
            InlineKeyboardButton("📋 Мои объявления", callback_data="my_ads"),
            InlineKeyboardButton("💬 Мои сообщения", callback_data="my_messages")
        ],
        [
            InlineKeyboardButton("🔔 Уведомления", callback_data="notifications"),
            InlineKeyboardButton("⭐ Отзывы", callback_data="feedback")
        ],
        [
            InlineKeyboardButton("❓ Помощь", callback_data="help"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="settings")
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


def ad_status_keyboard(ad_id: int) -> InlineKeyboardMarkup:
    """Keyboard for ad status actions."""
    keyboard = [
        [
            InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_ad_{ad_id}"),
            InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_ad_{ad_id}")
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data=f"stats_ad_{ad_id}"),
            InlineKeyboardButton("◀️ Назад", callback_data="my_ads")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def confirmation_keyboard(action: str, item_id: Optional[int] = None) -> InlineKeyboardMarkup:
    """Confirmation keyboard for destructive actions."""
    callback_data = f"confirm_{action}"
    if item_id:
        callback_data += f"_{item_id}"

    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data=callback_data),
            InlineKeyboardButton("❌ Нет", callback_data="cancel_action")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_keyboard() -> InlineKeyboardMarkup:
    """Admin panel keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("👁️ Модерация", callback_data="admin_moderation"),
            InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
            InlineKeyboardButton("📝 Объявления", callback_data="admin_ads")
        ],
        [
            InlineKeyboardButton("⭐ Отзывы", callback_data="admin_feedback"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")
        ],
        [
            InlineKeyboardButton("◀️ Назад", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
