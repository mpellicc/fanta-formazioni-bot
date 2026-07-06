import logging

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from fantaformazionibot.apptypes import BotApp
from fantaformazionibot.calendar.base import create_provider
from fantaformazionibot.config import TIMEZONE, Settings
from fantaformazionibot.models import Subscription
from fantaformazionibot.reminders.jobs import refresh_calendar, refresh_calendar_job
from fantaformazionibot.storage.repository import Repository
from fantaformazionibot.telegram.commands import (
    help_command,
    next_deadline_command,
    start_command,
    unknown_command,
)
from fantaformazionibot.telegram.errors import error_handler

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def _post_init(application: BotApp) -> None:
    """Seed the channel subscription, fetch the calendar, schedule reminders."""
    settings: Settings = application.bot_data["settings"]
    repository: Repository = application.bot_data["repository"]

    repository.upsert_subscription(
        Subscription(
            chat_id=settings.channel_chat_id,
            chat_type="channel",
            reminder_offsets=tuple(
                int(offset.total_seconds()) for offset in settings.reminder_offsets
            ),
        )
    )
    await refresh_calendar(application)


def run() -> None:
    setup_logging()
    settings = Settings()

    application = ApplicationBuilder().token(settings.token).post_init(_post_init).build()
    application.bot_data["settings"] = settings
    application.bot_data["repository"] = Repository(settings.database_path)
    application.bot_data["provider"] = create_provider(settings)

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("prossima_scadenza", next_deadline_command))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    application.add_error_handler(error_handler)

    job_queue = application.job_queue
    assert job_queue is not None
    job_queue.run_daily(
        refresh_calendar_job,
        time=settings.calendar_refresh_time.replace(tzinfo=TIMEZONE),
        name="calendar_refresh",
    )

    logger.info("Starting long polling")
    application.run_polling()
