from datetime import time
from typing import List

from config import Config
from db import database
from db.model.match import Match
from telegram.ext import ContextTypes, JobQueue
from utils.dates import get_clean_dates
from utils.logging import get_logger

# Get logger
logger = get_logger()


def schedule_jobs(config: Config, job_queue: JobQueue) -> None:
    logger.info("[JOB] Scheduling jobs...")

    job_queue.run_daily(
        update_matches_job, time=time(hour=1, minute=0, tzinfo=config.timezone), data={"config": config}
    )

    job_queue.run_repeating(
        send_notification_job, chat_id=config.channel_chat_id, interval=86400, first=0
    )


async def update_matches_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("[JOB][MATCHES][UPDATE] Starting job...")
    
    config: Config = context.job.data["config"]

    matches: List[Match] = get_clean_dates(config)
    database.save_matches(config.database_file, matches)


async def send_notification_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("[JOB][NOTIFICATION] Sending notification...")
    await context.bot.send_message(context.job.chat_id, text="Beep! Test message!")
