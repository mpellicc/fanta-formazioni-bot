from datetime import datetime

from dateutil import tz
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import Config
from constant.messages import Messages
from db import database
from db.model.match import Match
from utils.dates import (
    format_date_message,
    format_time_message,
    get_time_remaining_from_now
)


async def start_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends an introductory message."""
    await update.message.reply_text(Messages.START, parse_mode=ParseMode.MARKDOWN_V2)


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot."""
    await update.message.reply_text(Messages.HELP, parse_mode=ParseMode.MARKDOWN_V2)


async def next_match_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Sends a message indicating when the next match will be."""
    config: Config = context.bot_data["config"]

    next_match: Match = database.get_next_match(
        config.database_file,
        datetime.now(tz.tzutc()),
    )

    if next_match:
        await update.message.reply_text(
            Messages.NEXT_MATCH.format(
                match_date=format_date_message(next_match.match_datetime),
                match_time=format_time_message(next_match.match_datetime),
                deadline_str=get_time_remaining_from_now(next_match.match_datetime),
            ),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    else:
        await update.message.reply_text(
            Messages.NEXT_MATCH_NOT_FOUND, parse_mode=ParseMode.MARKDOWN_V2
        )
