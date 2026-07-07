from datetime import UTC, datetime, timedelta

from telegram import Chat, Message, Update
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.ext import ContextTypes

from fantaformazionibot.config import Settings
from fantaformazionibot.models import Subscription
from fantaformazionibot.reminders import planner
from fantaformazionibot.reminders.jobs import reschedule_reminders
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


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(messages.unknown_command(), parse_mode=ParseMode.HTML)
