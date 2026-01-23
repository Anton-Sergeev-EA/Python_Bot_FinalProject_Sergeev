from .start import register_handlers as register_start_handlers
from .ads import register_handlers as register_ad_handlers
from .search import register_handlers as register_search_handlers
from .moderation import register_handlers as register_moderation_handlers
from .feedback import register_handlers as register_feedback_handlers
from .notifications import register_handlers as register_notification_handlers

__all__ = [
    'register_start_handlers',
    'register_ad_handlers',
    'register_search_handlers',
    'register_moderation_handlers',
    'register_feedback_handlers',
    'register_notification_handlers'
]
