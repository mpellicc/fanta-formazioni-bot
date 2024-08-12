from config import Config
from telegram.ext import ContextTypes, JobQueue
from utils.logging import setup_logging

# Enable logging
logger = setup_logging()


def schedule_jobs(config: Config, job_queue: JobQueue) -> None:
    logger.debug("Scheduling jobs...")

    job_queue.run_repeating(
        send_notification_job, chat_id=config.channel_chat_id, interval=5, first=0
    )


async def send_notification_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("[JOB] Notification...")
    await context.bot.send_message(context.job.chat_id, text=f"Beep! Test message!")
