from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from telegram import Chat, Message, Update
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.ext import ContextTypes

from fantaformazionibot.config import Settings, parse_duration
from fantaformazionibot.models import Subscription
from fantaformazionibot.reminders import planner
from fantaformazionibot.reminders.jobs import reschedule_reminders
from fantaformazionibot.storage.repository import Repository
from fantaformazionibot.telegram import messages

MAX_OFFSETS = 10
MIN_OFFSET = timedelta(minutes=1)
MAX_OFFSET = timedelta(days=7)


class OffsetsParseError(ValueError):
    """Raised by parse_offsets_args; reason is mapped to Italian text in messages.py."""

    def __init__(self, reason: str, token: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.token = token


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


async def _sender_may_manage_subscription(
    message: Message, chat: Chat, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """In groups, only admins may toggle reminders (ADR 0012); elsewhere anyone."""
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return True
    # Anonymous admins post on behalf of the group itself.
    if message.sender_chat is not None and message.sender_chat.id == chat.id:
        return True
    if message.from_user is None:
        return False
    member = await context.bot.get_chat_member(chat.id, message.from_user.id)
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


def _to_timedeltas(offsets_seconds: tuple[int, ...]) -> tuple[timedelta, ...]:
    return tuple(timedelta(seconds=seconds) for seconds in offsets_seconds)


def parse_offsets_args(args: Sequence[str]) -> tuple[timedelta, ...]:
    """Parse /personalizza_orari arguments into validated, deduped, descending offsets.

    Tokens may be space- and/or comma-separated (PTB splits args on whitespace
    only, so a comma-joined list like "24h,1h" still needs a re-split here).
    """
    tokens = [token for part in args for token in part.split(",") if token]
    if not tokens:
        raise OffsetsParseError("empty")
    if len(tokens) > MAX_OFFSETS:
        raise OffsetsParseError("too_many")

    offsets: set[timedelta] = set()
    for token in tokens:
        try:
            offset = parse_duration(token)
        except ValueError as exc:
            raise OffsetsParseError("invalid_token", token) from exc
        if not (MIN_OFFSET <= offset <= MAX_OFFSET):
            raise OffsetsParseError("out_of_range", token)
        offsets.add(offset)

    return tuple(sorted(offsets, reverse=True))


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    chat = update.effective_chat
    if not await _sender_may_manage_subscription(update.message, chat, context):
        await update.message.reply_text(messages.admin_only(), parse_mode=ParseMode.HTML)
        return

    settings: Settings = context.bot_data["settings"]
    repository: Repository = context.bot_data["repository"]

    existing = repository.get_subscription(chat.id)
    if existing is not None:
        # Never overwrite offsets: custom times must survive a repeated /promemoria_on.
        await update.message.reply_text(
            messages.subscription_already_enabled(_to_timedeltas(existing.reminder_offsets)),
            parse_mode=ParseMode.HTML,
        )
        return

    repository.upsert_subscription(
        Subscription(
            chat_id=chat.id,
            chat_type=chat.type,
            reminder_offsets=tuple(
                int(offset.total_seconds()) for offset in settings.reminder_offsets
            ),
            origin="user",
        )
    )
    reschedule_reminders(context.application)
    await update.message.reply_text(
        messages.subscription_enabled(settings.reminder_offsets), parse_mode=ParseMode.HTML
    )


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    chat = update.effective_chat
    if not await _sender_may_manage_subscription(update.message, chat, context):
        await update.message.reply_text(messages.admin_only(), parse_mode=ParseMode.HTML)
        return

    repository: Repository = context.bot_data["repository"]
    if not repository.delete_user_subscription(chat.id):
        await update.message.reply_text(
            messages.subscription_not_enabled(), parse_mode=ParseMode.HTML
        )
        return

    reschedule_reminders(context.application)
    await update.message.reply_text(messages.subscription_disabled(), parse_mode=ParseMode.HTML)


async def subscription_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    repository: Repository = context.bot_data["repository"]
    subscription = repository.get_subscription(update.effective_chat.id)
    if subscription is None:
        await update.message.reply_text(
            messages.subscription_not_enabled(), parse_mode=ParseMode.HTML
        )
        return
    await update.message.reply_text(
        messages.subscription_status(_to_timedeltas(subscription.reminder_offsets)),
        parse_mode=ParseMode.HTML,
    )


_OFFSETS_ERROR_MESSAGES = {
    "empty": lambda token: messages.offsets_invalid_empty(),
    "too_many": lambda token: messages.offsets_too_many(MAX_OFFSETS),
    "invalid_token": lambda token: messages.offsets_invalid_token(token),
    "out_of_range": lambda token: messages.offsets_out_of_range(token, MIN_OFFSET, MAX_OFFSET),
}


async def set_offsets_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    chat = update.effective_chat
    args = context.args or []
    repository: Repository = context.bot_data["repository"]

    if not args:
        subscription = repository.get_subscription(chat.id)
        current = (
            _to_timedeltas(subscription.reminder_offsets) if subscription is not None else None
        )
        await update.message.reply_text(messages.offsets_usage(current), parse_mode=ParseMode.HTML)
        return

    if not await _sender_may_manage_subscription(update.message, chat, context):
        await update.message.reply_text(messages.admin_only(), parse_mode=ParseMode.HTML)
        return

    settings: Settings = context.bot_data["settings"]

    is_reset = len(args) == 1 and args[0].lower() == "default"
    if is_reset:
        offsets = settings.reminder_offsets
    else:
        try:
            offsets = parse_offsets_args(args)
        except OffsetsParseError as exc:
            await update.message.reply_text(
                _OFFSETS_ERROR_MESSAGES[exc.reason](exc.token), parse_mode=ParseMode.HTML
            )
            return

    offsets_seconds = tuple(int(offset.total_seconds()) for offset in offsets)
    existing_subscription = repository.get_subscription(chat.id)
    if existing_subscription is not None:
        repository.update_subscription_offsets(chat.id, offsets_seconds)
    else:
        repository.upsert_subscription(
            Subscription(
                chat_id=chat.id,
                chat_type=chat.type,
                reminder_offsets=offsets_seconds,
                origin="user",
            )
        )
    reschedule_reminders(context.application)

    if is_reset:
        await update.message.reply_text(messages.offsets_reset(offsets), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            messages.offsets_updated(offsets, newly_subscribed=existing_subscription is None),
            parse_mode=ParseMode.HTML,
        )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(messages.unknown_command(), parse_mode=ParseMode.HTML)
