import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from telegram.ext import Application, ApplicationBuilder, Defaults, ContextTypes
from telegram.constants import ParseMode
from dotenv import load_dotenv

load_dotenv()

from bot.handlers.start import register_handlers as register_start_handlers
from bot.handlers.ads import register_handlers as register_ad_handlers
from bot.handlers.search import register_handlers as register_search_handlers
from bot.handlers.moderation import register_handlers as register_moderation_handlers
from bot.handlers.feedback import register_handlers as register_feedback_handlers
from bot.handlers.notifications import register_handlers as register_notification_handlers

from scheduler.jobs import setup_scheduler

from database.connection import db
from config import settings

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


async def post_init(application: Application):
    logger.info("Bot initialization completed")

    # Проверяю подключение к базе данных (без создания таблиц).
    try:
        with db.get_session() as session:
            session.execute("SELECT 1")
        logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

    try:
        setup_scheduler(application.bot)
        logger.info("Scheduler setup completed")
    except Exception as e:
        logger.error(f"Failed to setup scheduler: {e}")


async def post_shutdown(application: Application):
    logger.info("Bot shutdown completed")

    from scheduler.jobs import scheduler
    if scheduler:
        scheduler.stop()

    db.dispose_engine()


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

    try:
        if update and hasattr(update, 'effective_user'):
            try:
                await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text="😔 Произошла ошибка при обработке вашего запроса. "
                         "Пожалуйста, попробуйте еще раз или обратитесь в поддержку."
                )
            except:
                pass

        if isinstance(context.error, Exception) and str(context.error).lower().find("critical") != -1:
            for admin_id in settings.ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"⚠️ Критическая ошибка в боте:\n\n{context.error}"
                    )
                except:
                    pass

    except Exception as e:
        logger.error(f"Error in error handler: {e}")


async def main():
    logger.info("Starting Rent from Anton bot...")

    # Validate required settings
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN not found in environment variables")
        sys.exit(1)

    defaults = Defaults(
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
        block=False
    )

    application = (
        ApplicationBuilder()
        .token(settings.BOT_TOKEN)
        .defaults(defaults)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)
        .build()
    )

    application.add_error_handler(error_handler)

    logger.info("Registering handlers...")
    register_start_handlers(application)
    register_ad_handlers(application)
    register_search_handlers(application)
    register_moderation_handlers(application)
    register_feedback_handlers(application)
    register_notification_handlers(application)

    logger.info(f"Registered {len(application.handlers)} handler groups")

    logger.info("Bot is starting...")

    try:
        await application.initialize()
        await application.start()

        bot = await application.bot.get_me()
        logger.info(f"Bot @{bot.username} is running!")
        logger.info(f"Bot ID: {bot.id}")
        logger.info(f"Bot name: {bot.first_name}")

        await application.updater.start_polling(
            drop_pending_updates=True
        )

        await asyncio.Event().wait()

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped with error: {e}")
    finally:
        if application.running:
            await application.stop()
            await application.shutdown()

        logger.info("Bot shutdown completed")


if __name__ == "__main__":
    asyncio.run(main())
