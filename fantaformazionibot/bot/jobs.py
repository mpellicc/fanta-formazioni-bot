from datetime import datetime, time
from typing import List

from dateutil import tz
from telegram.ext import ContextTypes, JobQueue

from bot.handler.handlers import handle_lineup_notifications
from config import Config
from db import database
from db.model.match import Match
from utils.dates import get_clean_dates
from utils.logging import get_logger

logger = get_logger(__name__)


def schedule_jobs(config: Config, job_queue: JobQueue) -> None:
    """
    Schedule jobs for updating matches and sending notifications.
    """
    logger.info("Scheduling jobs...")

    """
    ! Temporarily disabled due to an error on the fixtures by fixturedownload.com
    ! Dates are not correct and have been manually updated on `fantaformazionibot.db` file
    ! present in resources folder
    """
    # job_queue.run_daily(
    #     update_matches_job,
    #     time=time(hour=1, minute=0, tzinfo=tz.gettz(config.timezone)),
    #     data={"config": config},
    # )

    job_queue.run_repeating(
        send_notification_job,
        chat_id=config.channel_chat_id,
        interval=5,
        first=0,
        data={"config": config},
    )


async def update_matches_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Job to update matches in the database.
    """
    logger.debug("[MATCHES_UPDATE] Starting job...")

    config: Config = context.job.data["config"]

    matches: List[Match] = get_clean_dates(config)
    database.save_matches(config.database_file, matches)


async def send_notification_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Job to send notifications for upcoming match.
    """
    logger.debug("[LINEUP_NOTIFICATION] Starting job...")

    config: Config = context.job.data["config"]

    next_match: Match = database.get_next_match(config.database_file, datetime.now(tz.tzutc()))

    if next_match is None:
        logger.info("[LINEUP_NOTIFICATION] No next match found")
        return

    sent_notifications = database.get_notifications_by_match_id(
        config.database_file, next_match.id
    )

    await handle_lineup_notifications(config, next_match, sent_notifications, context)
