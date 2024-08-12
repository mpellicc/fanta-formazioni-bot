from telegram.ext import JobQueue

from fantaformazionibot.utils.logging import setup_logging

# Enable logging
logger = setup_logging()


def schedule_jobs(job_queue: JobQueue) -> None:
    logger.debug("Scheduling jobs...")

    # job_queue.run_repeating(check_and_send_notifications, interval=5, first=0)
    # job_queue.run_daily(remove_expired_dates, time=time(1, 0, 0))
    return
