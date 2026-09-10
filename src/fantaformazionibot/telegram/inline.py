"""Inline mode: @bot in any chat shares the next deadline (ADR 0033).

A pure read: it never touches `subscriptions` nor the schedule. Inline updates
carry no chat at all — only `from_user` — which is why ALLOWED_CHAT_IDS cannot
gate them and `allowed_user_ids` exists, and why the chosen-result event is
recorded with `record_process_event` (DB only: the log line's `chat_id=` prefix
is a contract towards the dashboard, ADR 0028 §5).
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from telegram import (
    InlineQueryResult,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import ChosenInlineResultHandler, ContextTypes, InlineQueryHandler

from fantaformazionibot.apptypes import BotApp
from fantaformazionibot.config import Settings
from fantaformazionibot.reminders import planner
from fantaformazionibot.storage.repository import Repository
from fantaformazionibot.telegram import messages
from fantaformazionibot.telegram.events import record_process_event

RESULT_DEADLINE = "deadline"
RESULT_INVITE = "invite"
# Telegram may serve a cached result to other users; the deadline card carries a
# countdown, so it must not go stale by more than a few seconds (ADR 0033 §3).
CACHE_TIME = 30


def inline_allowed(user_id: int | None, allowed_user_ids: Sequence[int]) -> bool:
    """Whether this user may use the inline mode (ADR 0033 §2).

    Empty whitelist means open, exactly like allowed_chat_ids: that is production.
    Pure, so the table of cases is testable without Telegram.
    """
    if not allowed_user_ids:
        return True
    return user_id is not None and user_id in allowed_user_ids


def build_results(deadline_text: str, bot_username: str) -> list[InlineQueryResult]:
    """The two cards, in this order: information first, invitation second.

    The first result is what pressing enter without choosing sends, so it has to be
    the deadline, never the invite.
    """
    return [
        InlineQueryResultArticle(
            id=RESULT_DEADLINE,
            title=messages.INLINE_DEADLINE_TITLE,
            input_message_content=InputTextMessageContent(deadline_text, parse_mode=ParseMode.HTML),
        ),
        InlineQueryResultArticle(
            id=RESULT_INVITE,
            title=messages.INLINE_INVITE_TITLE,
            description=messages.INLINE_INVITE_DESCRIPTION,
            input_message_content=InputTextMessageContent(
                messages.inline_invite(bot_username), parse_mode=ParseMode.HTML
            ),
        ),
    ]


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query
    if query is None:
        return
    settings: Settings = context.bot_data["settings"]
    if not inline_allowed(
        query.from_user.id if query.from_user else None, settings.allowed_user_ids
    ):
        # An empty answer is Telegram's "no results" — it does not reveal the bot.
        await query.answer([], cache_time=CACHE_TIME)
        return

    repository: Repository = context.bot_data["repository"]
    upcoming = planner.next_deadline(
        repository.get_matchdays(), settings.deadline_margin, datetime.now(UTC)
    )
    # The season can be over; the card keeps its slot rather than leaving an empty list.
    if upcoming is None:
        deadline_text = messages.no_upcoming_deadline()
    else:
        matchday, deadline = upcoming
        deadline_text = messages.next_deadline(matchday.round, deadline, datetime.now(UTC))

    # The query text is deliberately ignored (ADR 0033): this is a card to share,
    # not a search surface.
    await query.answer(build_results(deadline_text, context.bot.username), cache_time=CACHE_TIME)


async def chosen_inline_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """One row per actual share. Requires BotFather's /setinlinefeedback: without it
    this update never arrives and the feature simply goes unmeasured."""
    chosen = update.chosen_inline_result
    if chosen is None:
        return
    repository: Repository = context.bot_data["repository"]
    # The id comes back from the results we served, but it lands in an `outcome=`
    # the dashboard groups by: pin it to the known set rather than trust the echo.
    outcome = (
        chosen.result_id if chosen.result_id in (RESULT_DEADLINE, RESULT_INVITE) else "unknown"
    )
    record_process_event(
        repository,
        "inline_share",
        outcome,
        user_id=chosen.from_user.id if chosen.from_user else None,
    )


def register(application: BotApp) -> None:
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(ChosenInlineResultHandler(chosen_inline_result))
