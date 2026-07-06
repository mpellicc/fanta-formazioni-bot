import html
import json
import logging
import traceback

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from fantaformazionibot.config import Settings

logger = logging.getLogger(__name__)

# Keep the report well under Telegram's 4096-character message limit.
_TRACEBACK_BUDGET = 2800
_UPDATE_BUDGET = 700


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

    tb = "".join(traceback.format_exception(context.error)) if context.error else "no traceback"
    update_repr = (
        json.dumps(update.to_dict(), indent=2, ensure_ascii=False)
        if isinstance(update, Update)
        else str(update)
    )
    text = (
        "⚠️ <b>Exception while handling an update</b>\n\n"
        f"<pre>{html.escape(tb[-_TRACEBACK_BUDGET:])}</pre>\n"
        f"<pre>{html.escape(update_repr[:_UPDATE_BUDGET])}</pre>"
    )

    settings: Settings = context.bot_data["settings"]
    try:
        await context.bot.send_message(
            chat_id=settings.debug_chat_id, text=text, parse_mode=ParseMode.HTML
        )
    except Exception:
        logger.exception("Failed to report the error to the debug chat")
