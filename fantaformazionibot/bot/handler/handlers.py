from datetime import datetime, timedelta
from typing import List, Union

from config import Config
from constant.constants import NOTIFICATIONS_TIMES
from constant.messages import Messages
from db import database
from db.model.match import Match
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from utils.dates import get_time_remaining_from_now


async def default_response_handler(update: Update, _: ContextTypes.DEFAULT_TYPE) -> str:
    """Utility method to test the bot activeness."""
    text: str = update.message.text

    if "ciao" in text.lower():
        await update.message.reply_text("Ciao!")
        return

    await update.message.reply_text("Non capisco...")


async def handle_lineup_notifications(
    config: Config,
    next_match: Match,
    sent_notifications: List[int],
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Handle sending notifications based on the next match's notification times.
    """
    current_time = datetime.now(config.timezone)

    for seconds_from_expiry in NOTIFICATIONS_TIMES:
        notification_time = next_match.match_datetime - timedelta(
            seconds=seconds_from_expiry
        )
        if (
            _is_notification_due(notification_time, current_time)
            and seconds_from_expiry not in sent_notifications
        ):
            await _send_lineup_notification(context, config.channel_chat_id, next_match)
            database.record_notification_sent(
                config.database_file, next_match.id, seconds_from_expiry
            )


def _is_notification_due(notification_time: datetime, current_time: datetime) -> bool:
    """
    Check if the current time is within 30 seconds of the notification time.
    """
    return (
        (notification_time - timedelta(seconds=30))
        <= current_time
        < (notification_time + timedelta(seconds=30))
    )


async def _send_lineup_notification(
    context: ContextTypes.DEFAULT_TYPE, chat_id: Union[int, str], next_match: Match
) -> None:
    """
    Send a notification message to the specified chat.
    """

    await context.bot.send_message(
        text=Messages.LINEUP_NOTIFICATION.format(
            deadline_str=get_time_remaining_from_now(next_match.match_datetime),
        ),
        parse_mode=ParseMode.MARKDOWN_V2,
        chat_id=chat_id,
    )
