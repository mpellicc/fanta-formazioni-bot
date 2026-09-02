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
from fantaformazionibot.telegram.events import log_event

MAX_OFFSETS = 10
MIN_OFFSET = timedelta(minutes=1)
MAX_OFFSET = timedelta(days=7)


def bot_repository(context: ContextTypes.DEFAULT_TYPE) -> Repository:
    """The repository, for the permission gates that need it only to record an event."""
    repository: Repository = context.bot_data["repository"]
    return repository


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
    log_event(
        "lineup_confirm",
        chat_id,
        "noop" if already else "confirmed",
        repository=repository,
        round=round_,
    )
    return already


def undo_lineup_confirmation(
    chat_id: int, round_: int, repository: Repository, application: BotApp
) -> bool:
    """Core of the "Annulla conferma" button. Returns whether a confirmation was removed."""
    deleted = repository.unmark_lineup_confirmed(chat_id, round_)
    if deleted:
        reschedule_reminders(application)
    log_event(
        "lineup_undo",
        chat_id,
        "undone" if deleted else "noop",
        repository=repository,
        round=round_,
    )
    return deleted


@dataclass(frozen=True, slots=True)
class GroupConfirmResult:
    """Outcome of one manager confirming (or undoing) in a group. See ADR 0027."""

    already: bool
    confirmed: int
    total: int
    complete: bool
    roster_closed: bool


def join_roster(chat_id: int, user_id: int, repository: Repository, application: BotApp) -> bool:
    """Add a manager to the roster; returns whether they were new. No-op once closed.

    A new manager invalidates any "everyone confirmed" already reached, so the chat's
    silencing flags are dropped: reminders resume until the newcomer confirms too.
    """
    if repository.is_roster_closed(chat_id):
        log_event("roster_join", chat_id, "closed", repository=repository, user_id=user_id)
        return False
    if not repository.add_group_participant(chat_id, user_id):
        log_event("roster_join", chat_id, "noop", repository=repository, user_id=user_id)
        return False
    repository.clear_lineup_confirmations(chat_id)
    reschedule_reminders(application)
    log_event("roster_join", chat_id, "joined", repository=repository, user_id=user_id)
    return True


def _group_result(
    chat_id: int, round_: int, repository: Repository, *, already: bool
) -> GroupConfirmResult:
    return GroupConfirmResult(
        already=already,
        confirmed=repository.count_group_lineup_confirmations(chat_id, round_),
        total=repository.count_group_participants(chat_id),
        complete=repository.is_group_lineup_complete(chat_id, round_),
        roster_closed=repository.is_roster_closed(chat_id),
    )


def _sync_group_silencing(
    chat_id: int, round_: int, repository: Repository, application: BotApp, *, complete: bool
) -> None:
    """Keep the per-chat lineup_confirmations flag in sync with the roster (ADR 0027).

    Reusing that table as the derived silencing flag is what lets reminders/jobs.py keep
    its skip logic unchanged: it still only asks is_lineup_confirmed(chat_id, round).
    """
    silenced = repository.is_lineup_confirmed(chat_id, round_)
    if complete and not silenced:
        repository.mark_lineup_confirmed(chat_id, round_)
        reschedule_reminders(application)
    elif not complete and silenced:
        repository.unmark_lineup_confirmed(chat_id, round_)
        reschedule_reminders(application)


def reset_group_roster(chat_id: int, repository: Repository, application: BotApp) -> None:
    """Reopen enrollment from scratch (ADR 0027).

    An empty roster is never "complete", so every silencing flag for the chat has to go
    with it, otherwise a round stays muted with nobody left on the roster to unmute it.
    """
    repository.reopen_roster(chat_id)
    repository.clear_lineup_confirmations(chat_id)
    reschedule_reminders(application)
    log_event("roster_reset", chat_id, "reopened", repository=repository)


def confirm_group_lineup(
    chat_id: int, round_: int, user_id: int, repository: Repository, application: BotApp
) -> GroupConfirmResult:
    """Core of /ho_schierato and the glineup:confirm: callback in groups (ADR 0027).

    Confirming also enrols the presser while enrollment is open: that zero-setup fallback
    is what makes the feature work in groups that never run /iscrizioni.
    """
    already = repository.is_group_lineup_confirmed(chat_id, round_, user_id)
    if not repository.is_roster_closed(chat_id):
        # Zero-setup fallback: confirming enrols you. No flag reset needed here — the
        # _sync_group_silencing below recomputes completeness against the new roster.
        repository.add_group_participant(chat_id, user_id)
    if not already:
        repository.mark_group_lineup_confirmed(chat_id, round_, user_id)
    result = _group_result(chat_id, round_, repository, already=already)
    _sync_group_silencing(chat_id, round_, repository, application, complete=result.complete)
    log_event(
        "group_lineup_confirm",
        chat_id,
        "noop" if already else "confirmed",
        repository=repository,
        round=round_,
        user_id=user_id,
        confirmed=result.confirmed,
        total=result.total,
        complete=result.complete,
    )
    return result


def undo_group_lineup_confirmation(
    chat_id: int, round_: int, user_id: int, repository: Repository, application: BotApp
) -> GroupConfirmResult:
    """Core of the group "Annulla conferma" button: removes the presser's own row only."""
    deleted = repository.unmark_group_lineup_confirmed(chat_id, round_, user_id)
    result = _group_result(chat_id, round_, repository, already=not deleted)
    _sync_group_silencing(chat_id, round_, repository, application, complete=result.complete)
    log_event(
        "group_lineup_undo",
        chat_id,
        "undone" if deleted else "noop",
        repository=repository,
        round=round_,
        user_id=user_id,
        confirmed=result.confirmed,
        total=result.total,
    )
    return result


async def lineup_confirmed_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    chat = update.effective_chat
    if chat.type == ChatType.CHANNEL:
        return

    settings: Settings = context.bot_data["settings"]
    repository: Repository = context.bot_data["repository"]
    now = datetime.now(UTC)
    upcoming = planner.next_deadline(repository.get_matchdays(), settings.deadline_margin, now)
    if upcoming is None:
        await update.message.reply_text(messages.no_upcoming_deadline(), parse_mode=ParseMode.HTML)
        return

    matchday, _ = upcoming

    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        if update.message.from_user is None:
            return
        result = confirm_group_lineup(
            chat.id, matchday.round, update.message.from_user.id, repository, context.application
        )
        await update.message.reply_text(
            messages.group_lineup_confirmed(matchday.round, result),
            parse_mode=ParseMode.HTML,
            reply_markup=keyboards.build_group_lineup_keyboard(
                matchday.round, result.confirmed, result.total
            ),
        )
        return

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


async def roster_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/iscrizioni: roster status and enrollment controls for a group (ADR 0027)."""
    if update.message is None or update.effective_chat is None:
        return
    chat = update.effective_chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text(messages.roster_group_only(), parse_mode=ParseMode.HTML)
        return

    repository: Repository = context.bot_data["repository"]
    closed = repository.is_roster_closed(chat.id)
    await update.message.reply_text(
        messages.roster_status(repository.count_group_participants(chat.id), closed=closed),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboards.build_roster_keyboard(closed=closed),
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
        log_event(
            "permission_check",
            chat.id,
            "denied",
            repository=bot_repository(context),
            reason="no_sender",
        )
        return False
    allowed = await user_may_manage_subscription(message.from_user.id, chat, context)
    if not allowed:
        log_event(
            "permission_check",
            chat.id,
            "denied",
            repository=bot_repository(context),
            reason="not_admin",
            user_id=message.from_user.id,
        )
    return allowed


def _to_timedeltas(offsets_seconds: tuple[int, ...]) -> tuple[timedelta, ...]:
    return tuple(timedelta(seconds=seconds) for seconds in offsets_seconds)


def topic_thread_id(message: Message | None) -> int | None:
    """The forum topic a message lives in, if any (ADR 0025).

    In forums, messages posted in "General" have is_topic_message False: there
    the thread id is left None, so delivery stays identical to today.
    """
    if message is not None and message.is_topic_message and message.message_thread_id is not None:
        return message.message_thread_id
    return None


def topic_suffix(topic_changed: bool, message_thread_id: int | None) -> str:
    """Feedback fragment for a destination change, or "" when nothing moved.

    The caller already knows message_thread_id, so it (not subscribe/set_offsets)
    picks which of the two directions to announce.
    """
    if not topic_changed:
        return ""
    return (
        messages.subscription_topic_bound()
        if message_thread_id is not None
        else messages.subscription_topic_unbound()
    )


@dataclass(frozen=True, slots=True)
class SubscribeResult:
    already_subscribed: bool
    reminder_offsets: tuple[timedelta, ...]
    topic_changed: bool = False


def subscribe(
    chat: Chat,
    settings: Settings,
    repository: Repository,
    application: BotApp,
    message_thread_id: int | None = None,
) -> SubscribeResult:
    """Core of /promemoria_on, shared with the sub:on callback (telegram/callbacks.py)."""
    existing = repository.get_subscription(chat.id)
    if existing is not None:
        # Never overwrite offsets: custom times must survive a repeated subscribe.
        topic_changed = message_thread_id != existing.message_thread_id
        if topic_changed:
            # Destination only, not scheduling: PlannedReminder carries no thread id and
            # send_reminder_job re-reads the subscription (and its thread) at send time.
            repository.update_subscription_thread(chat.id, message_thread_id)
        log_event(
            "subscribe",
            chat.id,
            "noop",
            repository=repository,
            chat_type=chat.type,
            topic_changed=topic_changed,
            thread_id=message_thread_id,
        )
        return SubscribeResult(True, _to_timedeltas(existing.reminder_offsets), topic_changed)

    repository.upsert_subscription(
        Subscription(
            chat_id=chat.id,
            chat_type=chat.type,
            reminder_offsets=tuple(
                int(offset.total_seconds()) for offset in settings.reminder_offsets
            ),
            origin="user",
            message_thread_id=message_thread_id,
        )
    )
    reschedule_reminders(application)
    log_event(
        "subscribe",
        chat.id,
        "created",
        repository=repository,
        chat_type=chat.type,
        thread_id=message_thread_id,
    )
    return SubscribeResult(False, settings.reminder_offsets, message_thread_id is not None)


def unsubscribe(chat: Chat, repository: Repository, application: BotApp) -> bool:
    """Core of /promemoria_off, shared with the sub:off callback. Returns whether it existed."""
    deleted = repository.delete_user_subscription(chat.id)
    if deleted:
        reschedule_reminders(application)
    log_event(
        "unsubscribe",
        chat.id,
        "deleted" if deleted else "noop",
        repository=repository,
        chat_type=chat.type,
    )
    return deleted


@dataclass(frozen=True, slots=True)
class SetOffsetsResult:
    newly_subscribed: bool
    topic_changed: bool = False


def set_offsets(
    chat: Chat,
    offsets: tuple[timedelta, ...],
    repository: Repository,
    application: BotApp,
    message_thread_id: int | None = None,
) -> SetOffsetsResult:
    """Core of /personalizza_orari, shared with the offsets callbacks."""
    offsets_seconds = tuple(int(offset.total_seconds()) for offset in offsets)
    existing = repository.get_subscription(chat.id)
    # A brand-new row has no prior destination to compare against: only announce it when
    # a topic is actually being bound, matching subscribe()'s new-subscription case.
    topic_changed = (
        message_thread_id is not None
        if existing is None
        else message_thread_id != existing.message_thread_id
    )
    if existing is not None:
        repository.update_subscription_offsets(chat.id, offsets_seconds)
        if topic_changed:
            # Destination only, not scheduling: see subscribe()'s equivalent branch above.
            repository.update_subscription_thread(chat.id, message_thread_id)
    else:
        repository.upsert_subscription(
            Subscription(
                chat_id=chat.id,
                chat_type=chat.type,
                reminder_offsets=offsets_seconds,
                origin="user",
                message_thread_id=message_thread_id,
            )
        )
    reschedule_reminders(application)
    log_event(
        "set_offsets",
        chat.id,
        "created" if existing is None else "updated",
        repository=repository,
        chat_type=chat.type,
        offsets=",".join(str(seconds) for seconds in offsets_seconds),
        topic_changed=topic_changed,
        thread_id=message_thread_id,
    )
    return SetOffsetsResult(newly_subscribed=existing is None, topic_changed=topic_changed)


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
    thread_id = topic_thread_id(update.message)
    result = subscribe(chat, settings, repository, context.application, thread_id)

    if result.already_subscribed:
        text = messages.subscription_already_enabled(result.reminder_offsets)
    else:
        text = messages.subscription_enabled(result.reminder_offsets)
    text += topic_suffix(result.topic_changed, thread_id)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


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

    thread_id = topic_thread_id(update.message)
    result = set_offsets(chat, offsets, repository, context.application, thread_id)
    suffix = topic_suffix(result.topic_changed, thread_id)

    if is_reset:
        await update.message.reply_text(
            messages.offsets_reset(offsets) + suffix, parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            messages.offsets_updated(offsets, newly_subscribed=result.newly_subscribed) + suffix,
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
