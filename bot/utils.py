import re
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class InputValidator:
    """Validator for user input."""

    @staticmethod
    def validate_title(title: str) -> tuple[bool, str]:
        """Validate ad title."""
        if not title or len(title.strip()) == 0:
            return False, "Название не может быть пустым"

        title = title.strip()

        if len(title) < 3:
            return False, "Название слишком короткое (минимум 3 символа)"

        if len(title) > 200:
            return False, "Название слишком длинное (максимум 200 символов)"

        # Check for prohibited content.
        prohibited_patterns = [
            r"http[s]?://",  # URLs.
            r"@\w+",  # Mentions.
            r"#\w+",  # Hashtags.
        ]

        for pattern in prohibited_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                return False, "Название содержит запрещенные элементы"

        return True, title

    @staticmethod
    def validate_description(description: str) -> tuple[bool, str]:
        """Validate ad description."""
        if not description or len(description.strip()) == 0:
            return False, "Описание не может быть пустым"

        description = description.strip()

        if len(description) < 10:
            return False, "Описание слишком короткое (минимум 10 символов)"

        if len(description) > 5000:
            return False, "Описание слишком длинное (максимум 5000 символов)"

        # Check for spam patterns.
        spam_patterns = [
            r"\b(?:купи|продам|бесплатно|срочно|только сегодня)\b.*?\b(?:купи|продам|бесплатно|срочно|только сегодня)\b",
            r"!!!!!!!!+",
            r"\b[A-Z]{5,}\b",  # ALL CAPS WORDS.
        ]

        for pattern in spam_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                logger.warning(f"Spam detected in description: {pattern}")
                # Don't reject, just log for moderation.

        return True, description

    @staticmethod
    def validate_price(price_str: str, min_price: float = 0, max_price: float = 1000000) -> tuple[bool, float]:
        """Validate price."""
        try:
            # Clean the input.
            price_str = price_str.replace(',', '.').strip()

            # Remove currency symbols and extra spaces.
            price_str = re.sub(r'[^\d.]', '', price_str)

            if not price_str:
                return False, 0

            price = float(price_str)

            if price < min_price:
                return False, f"Цена не может быть меньше {min_price}"

            if price > max_price:
                return False, f"Цена не может быть больше {max_price}"

            # Round to 2 decimal places.
            price = round(price, 2)

            return True, price

        except (ValueError, InvalidOperation):
            return False, "Неверный формат цены. Используйте числа, например: 1000 или 1500.50"

    @staticmethod
    def validate_location(location: str) -> tuple[bool, str]:
        """Validate location."""
        if not location or len(location.strip()) == 0:
            return False, "Местоположение не может быть пустым"

        location = location.strip()

        if len(location) < 2:
            return False, "Местоположение слишком короткое"

        if len(location) > 200:
            return False, "Местоположение слишком длинное"

        return True, location

    @staticmethod
    def validate_contact_info(contact_info: str) -> tuple[bool, str]:
        """Validate contact information."""
        if not contact_info or len(contact_info.strip()) == 0:
            return False, "Контактная информация не может быть пустой"

        contact_info = contact_info.strip()

        if len(contact_info) < 3:
            return False, "Контактная информация слишком короткая"

        if len(contact_info) > 500:
            return False, "Контактная информация слишком длинная"

        # Check for valid contact methods.
        has_valid_contact = False

        # Check for Telegram username.
        if re.search(r'@[a-zA-Z0-9_]{5,32}', contact_info):
            has_valid_contact = True

        # Check for phone number (various formats).
        phone_patterns = [
            r'\+?[0-9\s\-\(\)]{7,20}',  # International and local.
            r'[0-9]{10,11}',  # Just digits.
        ]

        for pattern in phone_patterns:
            if re.search(pattern, contact_info):
                has_valid_contact = True
                break

        # Check for email.
        if re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', contact_info):
            has_valid_contact = True

        if not has_valid_contact:
            return False, "Пожалуйста, укажите действительный контакт (Telegram @username, телефон или email)"

        return True, contact_info

    @staticmethod
    def sanitize_input(text: str) -> str:
        """Sanitize user input to prevent injection attacks."""
        if not text:
            return text

        # Remove potentially dangerous characters.
        text = text.strip()

        # Replace multiple spaces with single space.
        text = re.sub(r'\s+', ' ', text)

        # Remove script tags and other HTML.
        text = re.sub(r'<[^>]*>', '', text)

        # Escape special characters for MarkdownV2.
        escape_chars = '_*[]()~`>#+-=|{}.!'
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')

        return text


class Formatter:
    """Formatter for various outputs."""

    @staticmethod
    def format_price(price: float) -> str:
        """Format price with thousands separators."""
        try:
            return f"{price:,.2f}".replace(',', ' ').replace('.', ',') + ' ₽'
        except:
            return str(price)

    @staticmethod
    def format_ad_preview(ad: Dict[str, Any]) -> str:
        """Format ad preview for display"""
        title = ad.get('title', 'Без названия')
        price = ad.get('price', 0)
        location = ad.get('location', 'Не указано')
        created_at = ad.get('created_at', datetime.now())

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

        time_ago = Formatter.time_ago(created_at)

        text = (
            f"*{Formatter.escape_markdown(title)}*\n\n"
            f"💰 *Цена:* {Formatter.format_price(price)}\n"
            f"📍 *Местоположение:* {Formatter.escape_markdown(location)}\n"
            f"🕐 *Опубликовано:* {time_ago}\n"
        )

        return text

    @staticmethod
    def format_ad_full(ad: Dict[str, Any], show_contacts: bool = False) -> str:
        """Format full ad information."""
        title = ad.get('title', 'Без названия')
        description = ad.get('description', 'Без описания')
        price = ad.get('price', 0)
        location = ad.get('location', 'Не указано')
        contact_info = ad.get('contact_info', 'Не указаны')
        created_at = ad.get('created_at', datetime.now())
        status = ad.get('status', 'active')

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

        time_ago = Formatter.time_ago(created_at)

        # Status emoji.
        status_emoji = {
            'draft': '📝',
            'pending': '⏳',
            'approved': '✅',
            'rejected': '❌',
            'rented': '🎉',
            'archived': '📁'
        }.get(status, '❓')

        text = (
            f"{status_emoji} *{Formatter.escape_markdown(title)}*\n\n"
            f"📋 *Описание:*\n{Formatter.escape_markdown(description)}\n\n"
            f"💰 *Цена:* {Formatter.format_price(price)}\n"
            f"📍 *Местоположение:* {Formatter.escape_markdown(location)}\n"
        )

        if show_contacts:
            text += f"📞 *Контакты:* {Formatter.escape_markdown(contact_info)}\n"
        else:
            text += f"📞 *Контакты:* [Нажмите для просмотра]({ad.get('id')})\n"

        text += f"🕐 *Опубликовано:* {time_ago}\n"
        text += f"🆔 *ID:* `{ad.get('id', 'N/A')}`"

        return text

    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escape special MarkdownV2 characters."""
        if not text:
            return text

        escape_chars = '_*[]()~`>#+-=|{}.!'
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')

        return text

    @staticmethod
    def time_ago(dt: datetime) -> str:
        """Convert datetime to time ago string."""
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt

        if diff.days > 365:
            years = diff.days // 365
            return f"{years} год{'а' if years % 10 in [2, 3, 4] and years % 100 not in [12, 13, 14] else 'ов'} назад"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} месяц{'а' if months % 10 in [2, 3, 4] and months % 100 not in [12, 13, 14] else 'ев'} назад"
        elif diff.days > 0:
            return f"{diff.days} день{'я' if diff.days % 10 in [2, 3, 4] and diff.days % 100 not in [12, 13, 14] else 'ей'} назад"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} час{'а' if hours % 10 in [2, 3, 4] and hours % 100 not in [12, 13, 14] else 'ов'} назад"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} минут{'ы' if minutes % 10 in [2, 3, 4] and minutes % 100 not in [12, 13, 14] else ''} назад"
        else:
            return "только что"

    @staticmethod
    def format_notification(notification: Dict[str, Any]) -> str:
        """Format notification for display."""
        n_type = notification.get('type', '')
        title = notification.get('title', '')
        content = notification.get('content', '')
        created_at = notification.get('created_at', datetime.now())

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

        time_ago = Formatter.time_ago(created_at)

        # Type emoji.
        type_emoji = {
            'new_ad': '📝',
            'new_message': '💬',
            'ad_approved': '✅',
            'ad_rejected': '❌',
            'ad_rented': '🎉',
            'warning': '⚠️',
            'info': 'ℹ️'
        }.get(n_type, '🔔')

        text = f"{type_emoji} "

        if title:
            text += f"*{Formatter.escape_markdown(title)}*\n\n"

        text += f"{Formatter.escape_markdown(content)}\n\n"
        text += f"_{time_ago}_"

        return text

    @staticmethod
    def format_feedback(feedback: Dict[str, Any]) -> str:
        """Format feedback for display"""
        rating = feedback.get('rating', 0)
        comment = feedback.get('comment', '')
        created_at = feedback.get('created_at', datetime.now())
        user = feedback.get('user', {})

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

        time_ago = Formatter.time_ago(created_at)
        username = user.get('username', 'Аноним')

        # Rating stars.
        stars = '⭐' * rating + '☆' * (5 - rating)

        text = f"{stars}\n"

        if comment:
            text += f"\n💬 *Комментарий:*\n{Formatter.escape_markdown(comment)}\n"

        text += f"\n👤 *От:* {Formatter.escape_markdown(username)}\n"
        text += f"🕐 *{time_ago}*"

        return text


class Security:
    """Security utilities."""

    @staticmethod
    def generate_session_token() -> str:
        """Generate random session token."""
        import secrets
        import string

        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32))

    @staticmethod
    def validate_session_token(token: str) -> bool:
        """Validate session token format."""
        if not token or len(token) != 32:
            return False

        # Check if token contains only valid characters.
        import string
        valid_chars = string.ascii_letters + string.digits
        return all(c in valid_chars for c in token)

    @staticmethod
    def rate_limit_key(user_id: int, action: str) -> str:
        """Generate rate limit key."""
        return f"rate_limit:{user_id}:{action}"

    @staticmethod
    def is_rate_limited(redis_client, key: str, limit: int, period: int) -> bool:
        """Check if user is rate limited."""
        try:
            import time
            current = int(time.time())
            window_start = current - period

            # Remove old entries.
            redis_client.zremrangebyscore(key, 0, window_start)

            # Count requests in current window.
            request_count = redis_client.zcard(key)

            if request_count >= limit:
                return True

            # Add current request.
            redis_client.zadd(key, {str(current): current})
            redis_client.expire(key, period)

            return False
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return False  # Don't limit if Redis fails.


class Cache:
    """Cache utilities."""

    @staticmethod
    def cache_key(prefix: str, **kwargs) -> str:
        """Generate cache key."""
        key_parts = [prefix]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}:{v}")
        return ":".join(key_parts)

    @staticmethod
    def get_cached(redis_client, key: str, ttl: int = 300):
        """Get cached value."""
        try:
            import json
            cached = redis_client.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Cache get failed: {e}")
        return None

    @staticmethod
    def set_cached(redis_client, key: str, value, ttl: int = 300):
        """Set cached value."""
        try:
            import json
            redis_client.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"Cache set failed: {e}")
            return False


# Initialize utility classes.
validator = InputValidator()
formatter = Formatter()
security = Security()
cache = Cache()
