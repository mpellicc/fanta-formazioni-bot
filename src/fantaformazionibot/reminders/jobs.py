"""JobQueue wiring: calendar refresh and exact-time reminder jobs. See ADR 0005."""

import logging
from datetime import UTC, datetime

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from fantaformazionibot.apptypes import BotApp
from fantaformazionibot.calendar.base import CalendarProvider
from fantaformazionibot.config import Settings
from fantaformazionibot.models import PlannedReminder
from fantaformazionibot.reminders import planner
from fantaformazionibot.storage.repository import Repository
from fantaformazionibot.telegram import messages

logger = logging.getLogger(__name__)

REMINDER_JOB_PREFIX = "reminder:"


async def refresh_calendar_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    await refresh_calendar(context.application)


async def refresh_calendar(application: BotApp) -> None:
    """Fetch the season calendar, upsert it, and rebuild the reminder schedule."""
    provider: CalendarProvider = application.bot_data["provider"]
    repository: Repository = application.bot_data["repository"]

    try:
        matchdays = await provider.fetch_matchdays()
    except Exception:
        # Keep whatever is already in the DB; reminders reschedule from it below.
        logger.exception("Calendar fetch failed, keeping existing matchdays")
    else:
        repository.upsert_matchdays(matchdays)
        logger.info("Calendar refreshed: %d matchdays", len(matchdays))

    reschedule_reminders(application)


def reschedule_reminders(application: BotApp) -> None:
    """Drop every scheduled reminder job and rebuild the plan from the DB."""
    job_queue = application.job_queue
    assert job_queue is not None

    for job in job_queue.jobs():
        if job.name and job.name.startswith(REMINDER_JOB_PREFIX):
            job.schedule_removal()

    settings: Settings = application.bot_data["settings"]
    repository: Repository = application.bot_data["repository"]

    plan = planner.plan_reminders(
        repository.get_matchdays(),
        repository.get_subscriptions(),
        settings.deadline_margin,
        datetime.now(UTC),
    )

    scheduled = 0
    for reminder in plan:
        if repository.was_reminder_sent(reminder.chat_id, reminder.round, reminder.offset_seconds):
            continue
        job_queue.run_once(
            send_reminder_job,
            when=reminder.when,
            name=f"{REMINDER_JOB_PREFIX}{reminder.chat_id}:{reminder.round}:{reminder.offset_seconds}",
            data=reminder,
        )
        scheduled += 1

    logger.info("Scheduled %d reminders", scheduled)


async def send_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    assert job is not None
    reminder = job.data
    assert isinstance(reminder, PlannedReminder)

    settings: Settings = context.bot_data["settings"]
    repository: Repository = context.bot_data["repository"]

    if repository.was_reminder_sent(reminder.chat_id, reminder.round, reminder.offset_seconds):
        return

    matchday = repository.get_matchday(reminder.round)
    if matchday is None:
        logger.warning("Matchday %d no longer in DB, skipping reminder", reminder.round)
        return

    now = datetime.now(UTC)
    deadline = planner.deadline_for(matchday, settings.deadline_margin)
    await context.bot.send_message(
        chat_id=reminder.chat_id,
        text=messages.reminder(matchday.round, deadline, now),
        parse_mode=ParseMode.HTML,
    )
    repository.mark_reminder_sent(reminder.chat_id, reminder.round, reminder.offset_seconds)
    logger.info(
        "Reminder sent to %d for round %d (offset %ds)",
        reminder.chat_id,
        reminder.round,
        reminder.offset_seconds,
    )
