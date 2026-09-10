"""Welcome message when the bot is added to a group (ADR 0032).

Neither a command nor a callback, hence its own module. The handler only ever
sends a message: being added is not consent to receive reminders, so no
subscription is created here (ADR 0012 keeps that an admin's explicit act).
"""

from telegram import ChatMemberUpdated, Update
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.ext import ChatMemberHandler, ContextTypes

from fantaformazionibot.apptypes import BotApp
from fantaformazionibot.config import Settings
from fantaformazionibot.storage.repository import Repository
from fantaformazionibot.telegram import keyboards, messages
from fantaformazionibot.telegram.events import log_event

_IN_CHAT = (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR)
_OUT_OF_CHAT = (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED)

GROUP_CHAT_TYPES = (ChatType.GROUP, ChatType.SUPERGROUP)


def is_bot_added(update: ChatMemberUpdated) -> bool:
    """Whether this my_chat_member update is the bot actually entering the chat.

    Pure, so the transition table is testable without Telegram. my_chat_member also
    fires when the bot is promoted to admin, demoted, or has its permissions edited
    while already in the chat: those must not re-trigger the welcome, so only a real
    out-of-chat → in-chat transition counts.
    """
    return (
        update.old_chat_member.status in _OUT_OF_CHAT and update.new_chat_member.status in _IN_CHAT
    )


async def bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    membership = update.my_chat_member
    if membership is None or not is_bot_added(membership):
        return
    chat = membership.chat
    if chat.type not in GROUP_CHAT_TYPES:
        # Channels are seeded by _post_init with origin='env'; in private chats the
        # entrance *is* /start.
        return

    repository: Repository = context.bot_data["repository"]
    settings: Settings = context.bot_data["settings"]
    # ChatMemberHandler takes no `filters`, so app.py's ALLOWED_CHAT_IDS gate has to be
    # re-checked here, the way _gate does it for callback queries.
    if settings.allowed_chat_ids and chat.id not in settings.allowed_chat_ids:
        log_event("bot_added", chat.id, "skipped", repository=repository, chat_type=chat.type)
        return

    # Re-added to a chat whose subscription survived: the toggle must show the truth.
    subscribed = repository.get_subscription(chat.id) is not None
    await context.bot.send_message(
        chat.id,
        messages.group_welcome(settings.reminder_offsets),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboards.build_subscription_keyboard(subscribed=subscribed),
    )
    log_event("bot_added", chat.id, "welcomed", repository=repository, chat_type=chat.type)


def register(application: BotApp) -> None:
    application.add_handler(ChatMemberHandler(bot_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER))
