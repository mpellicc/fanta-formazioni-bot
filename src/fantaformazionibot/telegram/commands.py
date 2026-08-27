from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from telegram import Chat, Message, Update
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.ext import ContextTypes

from fantaformazionibot.apptypes import BotApp
from fantaformazionibot.config import Settings, parse_duration
from fantaformazionibot.models import Subscription
from fantaformazionibot.reminders import planner
from fantaformazionibot.reminders.jobs import reschedule_reminders
from fantaformazionibot.storage.repository import Repository
from fantaformazionibot.telegram import keyboards, messages

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
    if update.message is None or update.effective_chat is None:
        return
    settings: Settings = context.bot_data["settings"]
    repository: Repository = context.bot_data["repository"]
    subscribed = repository.get_subscription(update.effective_chat.id) is not None
    await update.message.reply_text(
        messages.start(settings.reminder_offsets),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboards.build_subscription_keyboard(subscribed=subscribed),
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


def confirm_lineup(chat_id: int, round_: int, repository: Repository, application: BotApp) -> bool:
    """Core of /ho_schierato, shared with the lineup:confirm: callback. Returns whether it was
    already confirmed (idempotent: a repeat confirm is not an error)."""
    already = repository.is_lineup_confirmed(chat_id, round_)
    if not already:
        repository.mark_lineup_confirmed(chat_id, round_)
        reschedule_reminders(application)
    return already


def undo_lineup_confirmation(
    chat_id: int, round_: int, repository: Repository, application: BotApp
) -> bool:
    """Core of the "Annulla conferma" button. Returns whether a confirmation was removed."""
    deleted = repository.unmark_lineup_confirmed(chat_id, round_)
    if deleted:
        reschedule_reminders(application)
    return deleted


async def lineup_confirmed_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    chat = update.effective_chat
    if chat.type != ChatType.PRIVATE:
        await update.message.reply_text(messages.lineup_private_only(), parse_mode=ParseMode.HTML)
        return

    settings: Settings = context.bot_data["settings"]
    repository: Repository = context.bot_data["repository"]
    now = datetime.now(UTC)
    upcoming = planner.next_deadline(repository.get_matchdays(), settings.deadline_margin, now)
    if upcoming is None:
        await update.message.reply_text(messages.no_upcoming_deadline(), parse_mode=ParseMode.HTML)
        return

    matchday, _ = upcoming
    already = confirm_lineup(chat.id, matchday.round, repository, context.application)

    text = (
        messages.lineup_already_confirmed(matchday.round)
        if already
        else messages.lineup_confirmed(matchday.round)
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboards.build_lineup_confirmed_keyboard(matchday.round),
    )


async def user_may_manage_subscription(
    user_id: int, chat: Chat, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """In groups, only admins may toggle reminders (ADR 0012); elsewhere anyone.

    Shared by command handlers (via _sender_may_manage_subscription, which also
    handles the anonymous-admin case) and callback handlers (telegram/callbacks.py),
    where Telegram always reveals the real user on CallbackQuery.from_user even for
    anonymous admins, so no sender_chat check is needed there.
    """
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return True
    member = await context.bot.get_chat_member(chat.id, user_id)
    return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)


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
    return await user_may_manage_subscription(message.from_user.id, chat, context)


def _to_timedeltas(offsets_seconds: tuple[int, ...]) -> tuple[timedelta, ...]:
    return tuple(timedelta(seconds=seconds) for seconds in offsets_seconds)


@dataclass(frozen=True, slots=True)
class SubscribeResult:
    already_subscribed: bool
    reminder_offsets: tuple[timedelta, ...]


def subscribe(
    chat: Chat, settings: Settings, repository: Repository, application: BotApp
) -> SubscribeResult:
    """Core of /promemoria_on, shared with the sub:on callback (telegram/callbacks.py)."""
    existing = repository.get_subscription(chat.id)
    if existing is not None:
        # Never overwrite offsets: custom times must survive a repeated subscribe.
        return SubscribeResult(True, _to_timedeltas(existing.reminder_offsets))

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
    reschedule_reminders(application)
    return SubscribeResult(False, settings.reminder_offsets)


def unsubscribe(chat: Chat, repository: Repository, application: BotApp) -> bool:
    """Core of /promemoria_off, shared with the sub:off callback. Returns whether it existed."""
    deleted = repository.delete_user_subscription(chat.id)
    if deleted:
        reschedule_reminders(application)
    return deleted


def set_offsets(
    chat: Chat,
    offsets: tuple[timedelta, ...],
    repository: Repository,
    application: BotApp,
) -> bool:
    """Core of /personalizza_orari, shared with the offsets callbacks. Returns newly_subscribed."""
    offsets_seconds = tuple(int(offset.total_seconds()) for offset in offsets)
    existing = repository.get_subscription(chat.id)
    if existing is not None:
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
    reschedule_reminders(application)
    return existing is None


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
    result = subscribe(chat, settings, repository, context.application)

    if result.already_subscribed:
        await update.message.reply_text(
            messages.subscription_already_enabled(result.reminder_offsets),
            parse_mode=ParseMode.HTML,
        )
        return
    await update.message.reply_text(
        messages.subscription_enabled(result.reminder_offsets), parse_mode=ParseMode.HTML
    )


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    chat = update.effective_chat
    if not await _sender_may_manage_subscription(update.message, chat, context):
        await update.message.reply_text(messages.admin_only(), parse_mode=ParseMode.HTML)
        return

    repository: Repository = context.bot_data["repository"]
    if not unsubscribe(chat, repository, context.application):
        await update.message.reply_text(
            messages.subscription_not_enabled(), parse_mode=ParseMode.HTML
        )
        return
    await update.message.reply_text(messages.subscription_disabled(), parse_mode=ParseMode.HTML)


async def subscription_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    repository: Repository = context.bot_data["repository"]
    subscription = repository.get_subscription(update.effective_chat.id)
    if subscription is None:
        await update.message.reply_text(
            messages.subscription_not_enabled(),
            parse_mode=ParseMode.HTML,
            reply_markup=keyboards.build_subscription_keyboard(subscribed=False),
        )
        return
    await update.message.reply_text(
        messages.subscription_status(_to_timedeltas(subscription.reminder_offsets)),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboards.build_subscription_keyboard(subscribed=True),
    )


OFFSETS_ERROR_MESSAGES = {
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
    settings: Settings = context.bot_data["settings"]

    if not args:
        subscription = repository.get_subscription(chat.id)
        current = (
            _to_timedeltas(subscription.reminder_offsets) if subscription is not None else None
        )
        mask = keyboards.mask_from_offsets(
            subscription.reminder_offsets
            if subscription is not None
            else tuple(int(offset.total_seconds()) for offset in settings.reminder_offsets)
        )
        await update.message.reply_text(
            messages.offsets_usage(current),
            parse_mode=ParseMode.HTML,
            reply_markup=keyboards.build_offsets_keyboard(mask),
        )
        return

    if not await _sender_may_manage_subscription(update.message, chat, context):
        await update.message.reply_text(messages.admin_only(), parse_mode=ParseMode.HTML)
        return

    is_reset = len(args) == 1 and args[0].lower() == "default"
    if is_reset:
        offsets = settings.reminder_offsets
    else:
        try:
            offsets = parse_offsets_args(args)
        except OffsetsParseError as exc:
            await update.message.reply_text(
                OFFSETS_ERROR_MESSAGES[exc.reason](exc.token), parse_mode=ParseMode.HTML
            )
            return

    newly_subscribed = set_offsets(chat, offsets, repository, context.application)

    if is_reset:
        await update.message.reply_text(messages.offsets_reset(offsets), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            messages.offsets_updated(offsets, newly_subscribed=newly_subscribed),
            parse_mode=ParseMode.HTML,
        )


def is_addressed_to_other_bot(text: str, username: str) -> bool:
    """Groups often host multiple bots. A command can name its addressee
    ("/list@other_bot"); one naming someone else isn't ours to answer.
    Usernames are case-insensitive, as in PTB's own CommandHandler."""
    command = next(iter(text.split()), "")
    _, _, addressee = command.partition("@")
    return bool(addressee) and addressee.lower() != username.lower()


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.message.text is None:
        return
    if is_addressed_to_other_bot(update.message.text, context.bot.username):
        return
    await update.message.reply_text(messages.unknown_command(), parse_mode=ParseMode.HTML)
