"""
Планировщик задач для фоновых операций.
"""
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from database.crud import (
    ad_crud, notification_crud, search_query_crud,
    moderation_crud, user_crud
)
from database.models import AdStatus
from database.connection import db
from bot.utils import formatter
from config import settings

logger = logging.getLogger(__name__)


class JobScheduler:
    """Менеджер планировщика задач."""

    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.jobs = {}

    def start(self):
        """Запуск планировщика."""
        try:
            # Уведомления о новых объявлениях.
            self.scheduler.add_job(
                self.notify_new_ads,
                trigger=IntervalTrigger(
                    minutes=settings.NOTIFICATION_CHECK_INTERVAL
                ),
                id='notify_new_ads',
                name='Уведомления о новых объявлениях',
                replace_existing=True
            )

            # Оповещение модераторов.
            self.scheduler.add_job(
                self.notify_moderators,
                trigger=CronTrigger(hour='*/6'),  # Каждые 6 часов.
                id='notify_moderators',
                name='Оповещение модераторов',
                replace_existing=True
            )

            # Очистка старых данных.
            self.scheduler.add_job(
                self.cleanup_old_data,
                trigger=CronTrigger(hour=3),  # В 3 ночи
                id='cleanup_old_data',
                name='Очистка старых данных',
                replace_existing=True
            )

            # Статистика.
            self.scheduler.add_job(
                self.send_daily_stats,
                trigger=CronTrigger(hour=9, minute=0),  # В 9 утра
                id='daily_stats',
                name='Ежедневная статистика',
                replace_existing=True
            )

            # Проверка здоровья.
            self.scheduler.add_job(
                self.health_check,
                trigger=IntervalTrigger(minutes=5),
                id='health_check',
                name='Проверка здоровья',
                replace_existing=True
            )

            # Старт планировщика.
            self.scheduler.start()
            logger.info(f"Планировщик запущен с {len(self.scheduler.get_jobs())} задачами")

            # Запускаем все задачи немедленно для инициализации.
            asyncio.create_task(self.run_initial_jobs())

        except Exception as e:
            logger.error(f"Ошибка запуска планировщика: {e}")
            raise

    async def run_initial_jobs(self):
        """Запуск начальных задач."""
        try:
            logger.info("Запуск начальных задач...")
            await self.notify_new_ads()
            await self.health_check()
            logger.info("Начальные задачи выполнены")
        except Exception as e:
            logger.error(f"Ошибка выполнения начальных задач: {e}")

    async def notify_new_ads(self):
        """Уведомления о новых объявлениях."""
        try:
            logger.info("Запуск проверки новых объявлений для уведомлений...")

            with db.get_session() as session:
                # Получаем объявления за последние 10 минут.
                recent_ads = session.query(ad_crud.Ad).filter(
                    ad_crud.Ad.status == AdStatus.APPROVED,
                    ad_crud.Ad.created_at >= datetime.now() - timedelta(minutes=10)
                ).all()

                if not recent_ads:
                    logger.info("Нет новых объявлений для уведомлений")
                    return

                logger.info(f"Найдено {len(recent_ads)} новых объявлений")

                notified_count = 0

                for ad in recent_ads:
                    # Получаем поисковые запросы, соответствующие объявлению.
                    matching_queries = search_query_crud.get_queries_for_notification(session, ad)

                    if not matching_queries:
                        continue

                    # Отправляем уведомления пользователям.
                    for query in matching_queries:
                        try:
                            user = query.user

                            # Формируем сообщение.
                            message_text = (
                                f"🔔 *Новое объявление по вашему запросу!*\n\n"
                                f"{formatter.format_ad_preview({
                                    'title': ad.title,
                                    'price': ad.price,
                                    'location': ad.location,
                                    'created_at': ad.created_at
                                })}\n"
                                f"📌 *Ваши критерии:*\n"
                            )

                            if query.keywords:
                                message_text += f"• Ключевые слова: {query.keywords}\n"
                            if query.location:
                                message_text += f"• Местоположение: {query.location}\n"
                            if query.min_price:
                                message_text += f"• Цена от: {formatter.format_price(query.min_price)}\n"
                            if query.max_price:
                                message_text += f"• Цена до: {formatter.format_price(query.max_price)}\n"

                            message_text += f"\n[👁️ Просмотреть объявление]({ad.id})"

                            # Отправляем сообщение.
                            await self.bot.send_message(
                                chat_id=user.telegram_id,
                                text=message_text,
                                parse_mode='Markdown',
                                disable_web_page_preview=True
                            )

                            # Обновляем время последнего уведомления.
                            query.last_notified = datetime.now()
                            session.add(query)

                            notified_count += 1

                            # Задержка между уведомлениями чтобы не спамить.
                            await asyncio.sleep(0.1)

                        except Exception as e:
                            logger.error(f"Ошибка отправки уведомления пользователю {query.user_id}: {e}")
                            continue

                    # Сохраняем изменения после каждого объявления.
                    session.commit()

                logger.info(f"Отправлено {notified_count} уведомлений о новых объявлениях")

        except Exception as e:
            logger.error(f"Ошибка в задаче уведомлений: {e}")

    async def notify_moderators(self):
        """Оповещение модераторов о необработанных объявлениях."""
        try:
            logger.info("Проверка объявлений для модерации...")

            with db.get_session() as session:
                # Количество объявлений в очереди.
                pending_count = moderation_crud.get_pending_ads_count(session)

                if pending_count == 0:
                    logger.info("Нет объявлений для модерации")
                    return

                # Получаем старые объявления (> 24 часа в очереди).
                old_ads = session.query(moderation_crud.ModerationQueue).join(
                    ad_crud.Ad
                ).filter(
                    moderation_crud.ModerationQueue.created_at <= datetime.now() - timedelta(hours=24)
                ).all()

                if not old_ads and pending_count < 5:
                    logger.info(f"В очереди {pending_count} объявлений, но все новые")
                    return

                # Получаем список модераторов.
                moderators = session.query(user_crud.User).filter(
                    user_crud.User.role.in_(['moderator', 'admin'])
                ).all()

                if not moderators:
                    logger.warning("Нет модераторов для уведомления")
                    return

                # Формируем сообщение для модераторов.
                message_text = f"⚠️ *Требуется модерация!*\n\n"

                if old_ads:
                    message_text += f"⏰ *Старые объявления (>24ч):* {len(old_ads)}\n"
                    for i, entry in enumerate(old_ads[:3], 1):
                        message_text += f"{i}. '{entry.ad.title}' (ID: {entry.ad.id})\n"

                message_text += f"\n📋 *Всего в очереди:* {pending_count}\n"
                message_text += f"\n[👑 Перейти к модерации](moderation)"

                # Отправляем сообщение каждому модератору.
                sent_count = 0
                for moderator in moderators:
                    try:
                        await self.bot.send_message(
                            chat_id=moderator.telegram_id,
                            text=message_text,
                            parse_mode='Markdown'
                        )
                        sent_count += 1

                        # Задержка между отправками.
                        await asyncio.sleep(0.1)

                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления модератору {moderator.id}: {e}")
                        continue

                logger.info(f"Отправлено {sent_count} уведомлений модераторам")

        except Exception as e:
            logger.error(f"Ошибка в задаче оповещения модераторов: {e}")

    async def cleanup_old_data(self):
        """Очистка старых данных."""
        try:
            logger.info("Запуск очистки старых данных...")

            with db.get_session() as session:
                # Архивация старых объявлений (> 30 дней).
                thirty_days_ago = datetime.now() - timedelta(days=30)

                old_ads = session.query(ad_crud.Ad).filter(
                    ad_crud.Ad.status == AdStatus.APPROVED,
                    ad_crud.Ad.updated_at <= thirty_days_ago
                ).all()

                archived_count = 0
                for ad in old_ads:
                    ad.status = AdStatus.ARCHIVED
                    session.add(ad)
                    archived_count += 1

                # Очистка прочитанных уведомлений (> 7 дней).
                seven_days_ago = datetime.now() - timedelta(days=7)

                old_notifications = session.query(notification_crud.Notification).filter(
                    notification_crud.Notification.is_read == True,
                    notification_crud.Notification.created_at <= seven_days_ago
                ).all()

                deleted_notifications = 0
                for notification in old_notifications:
                    session.delete(notification)
                    deleted_notifications += 1

                # Очистка старых поисковых запросов (> 30 дней без использования).
                old_queries = session.query(search_query_crud.SearchQuery).filter(
                    search_query_crud.SearchQuery.last_notified <= thirty_days_ago
                ).all()

                deleted_queries = 0
                for query in old_queries:
                    session.delete(query)
                    deleted_queries += 1

                session.commit()

                logger.info(
                    f"Очистка завершена: "
                    f"архивировано {archived_count} объявлений, "
                    f"удалено {deleted_notifications} уведомлений, "
                    f"удалено {deleted_queries} поисковых запросов"
                )

        except Exception as e:
            logger.error(f"Ошибка очистки данных: {e}")

    async def send_daily_stats(self):
        """Отправка ежедневной статистики админам."""
        try:
            logger.info("Подготовка ежедневной статистики...")

            with db.get_session() as session:
                # Статистика за вчера.
                yesterday = datetime.now() - timedelta(days=1)
                yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
                yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)

                # Новые пользователи.
                new_users = session.query(user_crud.User).filter(
                    user_crud.User.created_at.between(yesterday_start, yesterday_end)
                ).count()

                # Новые объявления.
                new_ads = session.query(ad_crud.Ad).filter(
                    ad_crud.Ad.created_at.between(yesterday_start, yesterday_end)
                ).count()

                # Одобренные объявления.
                approved_ads = session.query(ad_crud.Ad).filter(
                    ad_crud.Ad.status == AdStatus.APPROVED,
                    ad_crud.Ad.moderated_at.between(yesterday_start, yesterday_end)
                ).count()

                # Новые сообщения.
                new_messages = session.query(message_crud.Message).filter(
                    message_crud.Message.created_at.between(yesterday_start, yesterday_end)
                ).count()

                # Новые отзывы.
                new_feedback = session.query(feedback_crud.Feedback).filter(
                    feedback_crud.Feedback.created_at.between(yesterday_start, yesterday_end)
                ).count()

                # Общая статистика.
                total_users = session.query(user_crud.User).count()
                total_ads = session.query(ad_crud.Ad).count()
                active_ads = session.query(ad_crud.Ad).filter(
                    ad_crud.Ad.status == AdStatus.APPROVED
                ).count()

                # Формируем отчет.
                report_date = yesterday.strftime("%d.%m.%Y")
                stats_text = (
                    f"📊 *Ежедневный отчет за {report_date}*\n\n"
                    f"📈 *Новые данные:*\n"
                    f"• 👥 Новые пользователи: {new_users}\n"
                    f"• 📝 Новые объявления: {new_ads}\n"
                    f"• ✅ Одобрено объявлений: {approved_ads}\n"
                    f"• 💬 Новые сообщения: {new_messages}\n"
                    f"• ⭐ Новые отзывы: {new_feedback}\n\n"
                    f"📋 *Общая статистика:*\n"
                    f"• 👥 Всего пользователей: {total_users}\n"
                    f"• 📝 Всего объявлений: {total_ads}\n"
                    f"• ✅ Активных объявлений: {active_ads}\n\n"
                    f"📅 *Следующий отчет:* завтра в 09:00"
                )

                # Получаем админов.
                admins = session.query(user_crud.User).filter(
                    user_crud.User.role == 'admin'
                ).all()

                if not admins:
                    admins = [user for user in session.query(user_crud.User).all()
                              if user.telegram_id in settings.ADMIN_IDS]

                # Отправляем отчет каждому админу.
                sent_count = 0
                for admin in admins:
                    try:
                        await self.bot.send_message(
                            chat_id=admin.telegram_id,
                            text=stats_text,
                            parse_mode='Markdown'
                        )
                        sent_count += 1

                        await asyncio.sleep(0.1)

                    except Exception as e:
                        logger.error(f"Ошибка отправки отчета админу {admin.id}: {e}")
                        continue

                logger.info(f"Отправлен ежедневный отчет {sent_count} админам")

        except Exception as e:
            logger.error(f"Ошибка подготовки ежедневной статистики: {e}")

    async def health_check(self):
        """Проверка здоровья системы."""
        try:
            with db.get_session() as session:
                # Проверка базы данных.
                db_check = session.execute("SELECT 1").scalar()

                # Статистика для мониторинга.
                users_count = session.query(user_crud.User).count()
                ads_count = session.query(ad_crud.Ad).count()
                pending_ads = session.query(ad_crud.Ad).filter(
                    ad_crud.Ad.status == AdStatus.PENDING
                ).count()

                health_status = {
                    'database': db_check == 1,
                    'users': users_count,
                    'ads': ads_count,
                    'pending_ads': pending_ads,
                    'timestamp': datetime.now().isoformat()
                }

                logger.debug(f"Health check: {health_status}")

                # Если есть проблемы, отправляем уведомление.
                if pending_ads > 20:  # Много объявлений в очереди.
                    logger.warning(f"Много объявлений в очереди: {pending_ads}")

                return health_status

        except Exception as e:
            logger.error(f"Ошибка проверки здоровья: {e}")
            return {
                'database': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def stop(self):
        """Остановка планировщика."""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("Планировщик остановлен")
        except Exception as e:
            logger.error(f"Ошибка остановки планировщика: {e}")


# Глобальный экземпляр планировщика.
scheduler = None


def setup_scheduler(bot):
    """Настройка планировщика."""
    global scheduler
    scheduler = JobScheduler(bot)
    scheduler.start()
    return scheduler
