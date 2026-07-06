from datetime import UTC, datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from fantaformazionibot.config import Settings
from fantaformazionibot.reminders import planner
from fantaformazionibot.storage.repository import Repository
from fantaformazionibot.telegram import messages


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    settings: Settings = context.bot_data["settings"]
    await update.message.reply_text(
        messages.start(settings.reminder_offsets), parse_mode=ParseMode.HTML
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(messages.help_(), parse_mode=ParseMode.HTML)


async def next_deadline_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    settings: Settings = context.bot_data["settings"]
    repository: Repository = context.bot_data["repository"]

    now = datetime.now(UTC)
    upcoming = planner.next_deadline(repository.get_matchdays(), settings.deadline_margin, now)

    if upcoming is None:
        await update.message.reply_text(messages.no_upcoming_deadline(), parse_mode=ParseMode.HTML)
        return

    matchday, deadline = upcoming
    await update.message.reply_text(
        messages.next_deadline(matchday.round, deadline, now), parse_mode=ParseMode.HTML
    )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(messages.unknown_command(), parse_mode=ParseMode.HTML)
