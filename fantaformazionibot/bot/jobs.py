import logging

from telegram.ext import JobQueue

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


def schedule_jobs(job_queue: JobQueue) -> None:
    # job_queue.run_repeating(check_and_send_notifications, interval=5, first=0)
    # job_queue.run_daily(remove_expired_dates, time=time(1, 0, 0))
    return
