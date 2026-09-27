import html
import json
import logging
import traceback
from collections import Counter
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
# Bad Gateway, ...) forever on its own, so reporting every blip to the debug
# chat is just noise. Those are only counted: a daily digest reports the noise,
# and a short alert fires only when polling keeps failing (ADR 0038). Any other
# error (handler/job bugs, BadRequest, Forbidden...) is still reported
# immediately, every time.
POLLING_OUTAGE_THRESHOLD = timedelta(minutes=5)
# PTB exposes no hook for a successful poll, so recovery is inferred from
# silence: longer than the worst gap between two failing polls (30s max backoff
# plus the request's own timeouts).
POLLING_RECOVERY_QUIET = timedelta(seconds=90)


class PollingNetworkMonitor:
    """In-memory tracking of polling network errors: outage streak + daily counts."""

    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.first_error_at: datetime | None = None
        self.last_error_at: datetime | None = None
        self.last_error: str = ""
        self.alerted = False

    def record(self, error: BaseException, now: datetime) -> None:
        kind = _error_kind(error)
        self.counts[kind] += 1
        if self.first_error_at is None:
            self.first_error_at = now
        self.last_error_at = now
        self.last_error = kind

    def check(self, now: datetime) -> str | None:
        """Advance the streak; return the debug-chat text to send, if any."""
        if self.first_error_at is None or self.last_error_at is None:
            return None
        if now - self.last_error_at > POLLING_RECOVERY_QUIET:
            duration = self.last_error_at - self.first_error_at
            text = (
                f"✅ Polling recovered after {_minutes(duration)} min of network errors."
                if self.alerted
                else None
            )
            self.first_error_at = self.last_error_at = None
            self.alerted = False
            return text
        if not self.alerted and now - self.first_error_at > POLLING_OUTAGE_THRESHOLD:
            self.alerted = True
            return (
                f"⚠️ Polling failing for {_minutes(now - self.first_error_at)} min "
                f"(last: {html.escape(self.last_error)})."
            )
        return None

    def digest(self) -> str | None:
        """Return the last period's noise summary and reset the counts."""
        if not self.counts:
            return None
        summary = ", ".join(f"{n}x {html.escape(kind)}" for kind, n in self.counts.most_common())
        self.counts.clear()
        return f"📶 Polling network noise, last 24h: {summary}."


def _error_kind(error: BaseException) -> str:
    # "httpx.ReadError: " / "Bad Gateway": the message is the useful part, minus details.
    return str(error).split(":", 1)[0].strip() or type(error).__name__


def _minutes(delta: timedelta) -> int:
    return max(1, round(delta.total_seconds() / 60))


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
    if _is_transient_polling_error(update, context):
        assert context.error is not None
        logger.warning("Polling network error: %s", context.error)
        monitor: PollingNetworkMonitor = context.bot_data["polling_monitor"]
        monitor.record(context.error, datetime.now(UTC))
        return

    logger.error("Exception while handling an update:", exc_info=context.error)

    if is_unwritable_chat_error(context.error):
        return

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


async def _send_to_debug_chat(context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    settings: Settings = context.bot_data["settings"]
    try:
        await context.bot.send_message(
            chat_id=settings.debug_chat_id, text=text, parse_mode=ParseMode.HTML
        )
    except Exception:
        logger.exception("Failed to send a polling network report to the debug chat")


async def polling_outage_check_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    monitor: PollingNetworkMonitor = context.bot_data["polling_monitor"]
    text = monitor.check(datetime.now(UTC))
    if text is not None:
        await _send_to_debug_chat(context, text)


async def polling_noise_digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    monitor: PollingNetworkMonitor = context.bot_data["polling_monitor"]
    text = monitor.digest()
    if text is not None:
        await _send_to_debug_chat(context, text)
