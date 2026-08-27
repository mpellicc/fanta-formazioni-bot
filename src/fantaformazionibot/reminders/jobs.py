"""JobQueue wiring: calendar refresh and exact-time reminder jobs. See ADR 0005."""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from fantaformazionibot.apptypes import BotApp
from fantaformazionibot.calendar.base import CalendarProvider
from fantaformazionibot.config import Settings
from fantaformazionibot.models import Matchday, PlannedReminder, Subscription
from fantaformazionibot.reminders import planner
from fantaformazionibot.storage.repository import Repository
from fantaformazionibot.telegram import keyboards, messages
from fantaformazionibot.telegram.errors import is_dead_chat_error

logger = logging.getLogger(__name__)

REMINDER_JOB_PREFIX = "reminder:"
STALE_KICKOFF_THRESHOLD = timedelta(days=3)


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

    await _alert_if_stale(application, repository.get_matchdays())
    reschedule_reminders(application)


async def _alert_if_stale(application: BotApp, matchdays: Sequence[Matchday]) -> None:
    """Warn the debug chat if the next matchday's kickoff still looks like a placeholder.

    See ADR 0014. No dedup: re-runs on every refresh and re-alerts while the
    condition holds, since this only reaches a private debug chat once a day.
    """
    settings: Settings = application.bot_data["settings"]
    stale = planner.stale_matchday(
        matchdays, settings.deadline_margin, datetime.now(UTC), STALE_KICKOFF_THRESHOLD
    )
    if stale is None:
        return

    logger.warning("Matchday %d still has a placeholder kickoff close to its deadline", stale.round)
    try:
        await application.bot.send_message(
            chat_id=settings.debug_chat_id,
            text=(
                f"⚠️ Matchday {stale.round} still has a placeholder kickoff (00:00 UTC) "
                f"with its deadline less than {STALE_KICKOFF_THRESHOLD.days} days away. "
                "fixturedownload may not have updated yet; consider switching CALENDAR_PROVIDER."
            ),
        )
    except Exception:
        logger.exception("Failed to send staleness alert to the debug chat")


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
        if repository.is_lineup_confirmed(reminder.chat_id, reminder.round):
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
    if repository.is_lineup_confirmed(reminder.chat_id, reminder.round):
        return

    matchday = repository.get_matchday(reminder.round)
    if matchday is None:
        logger.warning("Matchday %d no longer in DB, skipping reminder", reminder.round)
        return

    now = datetime.now(UTC)
    deadline = planner.deadline_for(matchday, settings.deadline_margin)
    subscription = repository.get_subscription(reminder.chat_id)
    reply_markup = (
        keyboards.build_lineup_confirm_keyboard(reminder.round)
        if subscription is not None and subscription.chat_type == ChatType.PRIVATE
        else None
    )
    try:
        await context.bot.send_message(
            chat_id=reminder.chat_id,
            text=messages.reminder(
                matchday.round,
                deadline,
                now,
                reminder.offset_seconds,
                settings.urgent_reminder_threshold,
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )
    except Exception as exc:
        if not is_dead_chat_error(exc):
            raise
        await _prune_dead_chat(context, reminder.chat_id, subscription)
        return

    repository.mark_reminder_sent(reminder.chat_id, reminder.round, reminder.offset_seconds)
    logger.info(
        "Reminder sent to %d for round %d (offset %ds)",
        reminder.chat_id,
        reminder.round,
        reminder.offset_seconds,
    )


async def _prune_dead_chat(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, subscription: Subscription | None
) -> None:
    """Stop reminding a chat that can no longer receive them (ADR 0023).

    A user-owned subscription is dropped, silently as far as the debug chat is
    concerned: being blocked is churn, and /promemoria_on brings the chat back.
    The env-owned channel row is kept — _post_init re-seeds it on every restart,
    so deleting it would only postpone the same failure — and reported instead,
    since losing access to the configured channel needs a human.
    """
    settings: Settings = context.bot_data["settings"]
    repository: Repository = context.bot_data["repository"]

    if subscription is not None and subscription.origin == "env":
        logger.error("Cannot deliver reminders to the configured channel %d", chat_id)
        try:
            await context.bot.send_message(
                chat_id=settings.debug_chat_id,
                text=(
                    f"⚠️ Telegram is refusing reminders to the configured channel {chat_id}: "
                    "the bot was likely removed or its rights revoked. The subscription is "
                    "kept — restore the bot's access to resume delivery."
                ),
            )
        except Exception:
            logger.exception("Failed to report the dead channel to the debug chat")
        return

    repository.delete_user_subscription(chat_id)
    _cancel_reminders_for(context, chat_id)
    logger.warning("Subscription %d pruned: the chat no longer accepts our messages", chat_id)


def _cancel_reminders_for(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Drop the still-pending reminder jobs of a chat, by the name prefix
    reschedule_reminders builds them with."""
    job_queue = context.job_queue
    if job_queue is None:
        return
    prefix = f"{REMINDER_JOB_PREFIX}{chat_id}:"
    for job in job_queue.jobs():
        if job.name and job.name.startswith(prefix):
            job.schedule_removal()
