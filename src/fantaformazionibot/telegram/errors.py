import html
import json
import logging
import traceback
from datetime import UTC, datetime, timedelta

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, NetworkError
from telegram.ext import ContextTypes

from fantaformazionibot.config import Settings

logger = logging.getLogger(__name__)

# Keep the report well under Telegram's 4096-character message limit.
_TRACEBACK_BUDGET = 2800
_UPDATE_BUDGET = 700

# PTB's polling loop already retries plain network hiccups (httpx ReadError,
# TimedOut, ...) forever on its own, so reporting every blip to the debug chat
# is just noise. Throttle only that specific, already-self-healing case; any
# other error (handler/job bugs, BadRequest, Forbidden...) is still reported
# immediately, every time.
_POLLING_NETWORK_ERROR_COOLDOWN = timedelta(minutes=10)
_last_polling_network_error_notice: datetime | None = None

# Telegram refuses the delivery when the destination stopped accepting our
# messages. Nothing in the code can fix those and every send site can hit them,
# so they are logged but never reported. Matching on the description is the only
# option — PTB models these as one generic error class each — but it stays
# deliberately narrow: a BadRequest we *can* fix (a malformed HTML body, say)
# must still reach the debug chat.
#
# Terminal vs transient matters at the reminder send site, which prunes the
# subscription on the former and lets the latter pass (ADR 0023).
_DEAD_CHAT_DESCRIPTIONS = ("chat not found",)
_TRANSIENTLY_UNWRITABLE_DESCRIPTIONS = (
    "topic_closed",
    "topic_deleted",
    "message thread not found",
    "have no rights to send a message",
)


def _matches(error: BaseException | None, descriptions: tuple[str, ...]) -> bool:
    if not isinstance(error, BadRequest):
        return False
    return any(known in str(error).lower() for known in descriptions)


def is_dead_chat_error(error: BaseException | None) -> bool:
    """The chat will never accept our messages again: blocked, kicked, gone."""
    return isinstance(error, Forbidden) or _matches(error, _DEAD_CHAT_DESCRIPTIONS)


def is_unwritable_chat_error(error: BaseException | None) -> bool:
    """This delivery failed for a reason no code change can fix — dead chat, or
    a destination that may well accept the next message (a closed forum topic)."""
    return is_dead_chat_error(error) or _matches(error, _TRANSIENTLY_UNWRITABLE_DESCRIPTIONS)


def _is_transient_polling_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> bool:
    return (
        update is None
        and context.job is None
        and isinstance(context.error, NetworkError)
        and not isinstance(context.error, BadRequest)
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _last_polling_network_error_notice
    logger.error("Exception while handling an update:", exc_info=context.error)

    if is_unwritable_chat_error(context.error):
        return

    if _is_transient_polling_error(update, context):
        now = datetime.now(UTC)
        if (
            _last_polling_network_error_notice is not None
            and now - _last_polling_network_error_notice < _POLLING_NETWORK_ERROR_COOLDOWN
        ):
            return
        _last_polling_network_error_notice = now

    tb = "".join(traceback.format_exception(context.error)) if context.error else "no traceback"
    text = (
        "⚠️ <b>Exception while handling an update</b>\n\n"
        '<pre><code class="language-python">'
        f"{html.escape(tb[-_TRACEBACK_BUDGET:])}</code></pre>"
    )
    if isinstance(update, Update):
        update_repr = json.dumps(update.to_dict(), indent=2, ensure_ascii=False)
        text += (
            '\n<pre><code class="language-json">'
            f"{html.escape(update_repr[:_UPDATE_BUDGET])}</code></pre>"
        )

    settings: Settings = context.bot_data["settings"]
    try:
        await context.bot.send_message(
            chat_id=settings.debug_chat_id, text=text, parse_mode=ParseMode.HTML
        )
    except Exception:
        logger.exception("Failed to report the error to the debug chat")
