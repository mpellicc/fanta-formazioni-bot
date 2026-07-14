"""CallbackQueryHandler entry points and the custom-offsets conversation (ADR 0015).

Every handler here edits the pressed message in place (edit_message_text /
edit_message_reply_markup) rather than sending a new one, and always ends with
answer_callback_query as the toast. Which presets are checked in the offsets
grid lives entirely in callback_data as a bitmask (telegram/keyboards.py); only
the short-lived custom-input conversation needs `context.user_data`, to
remember which grid/prompt message (and prior mask) to restore on
save/cancel/timeout/back.
"""

import contextlib
import re
from datetime import timedelta

from telegram import CallbackQuery, Chat, ForceReply, InlineKeyboardMarkup, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from fantaformazionibot.apptypes import BotApp
from fantaformazionibot.config import Settings
from fantaformazionibot.storage.repository import Repository
from fantaformazionibot.telegram import keyboards, messages
from fantaformazionibot.telegram.commands import (
    OFFSETS_ERROR_MESSAGES,
    OffsetsParseError,
    confirm_lineup,
    parse_offsets_args,
    set_offsets,
    subscribe,
    undo_lineup_confirmation,
    unsubscribe,
    user_may_manage_subscription,
)

OFFSETS_CUSTOM_INPUT = 1

_GRID_CHAT_ID = "offsets_grid_chat_id"
_GRID_MESSAGE_ID = "offsets_grid_message_id"
_GRID_MASK = "offsets_grid_mask"
_PROMPT_MESSAGE_ID = "offsets_prompt_message_id"


async def _gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> CallbackQuery | None:
    """ALLOWED_CHAT_IDS silence (app.py's filters.Chat has no callback-query equivalent)."""
    query = update.callback_query
    if query is None or query.message is None:
        return None
    settings: Settings = context.bot_data["settings"]
    if settings.allowed_chat_ids and query.message.chat.id not in settings.allowed_chat_ids:
        await query.answer()
        return None
    return query


async def _may_manage(query: CallbackQuery, chat: Chat, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Admin check for callbacks (ADR 0012). CallbackQuery.from_user is always the real
    user, even for anonymous admins, so unlike commands there's no sender_chat case."""
    if query.from_user is None or not await user_may_manage_subscription(
        query.from_user.id, chat, context
    ):
        await query.answer(messages.admin_only(), show_alert=True)
        return False
    return True


async def _edit_text(query: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    with contextlib.suppress(BadRequest):
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def _edit_markup(query: CallbackQuery, reply_markup: InlineKeyboardMarkup) -> None:
    with contextlib.suppress(BadRequest):
        await query.edit_message_reply_markup(reply_markup=reply_markup)


async def subscribe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = await _gate(update, context)
    if query is None or query.message is None:
        return
    chat = query.message.chat
    if not await _may_manage(query, chat, context):
        return

    settings: Settings = context.bot_data["settings"]
    repository: Repository = context.bot_data["repository"]
    result = subscribe(chat, settings, repository, context.application)

    await query.answer()
    text = (
        messages.subscription_already_enabled(result.reminder_offsets)
        if result.already_subscribed
        else messages.subscription_enabled(result.reminder_offsets)
    )
    await _edit_text(query, text, keyboards.build_subscription_keyboard(subscribed=True))


async def unsubscribe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = await _gate(update, context)
    if query is None or query.message is None:
        return
    chat = query.message.chat
    if not await _may_manage(query, chat, context):
        return

    repository: Repository = context.bot_data["repository"]
    deleted = unsubscribe(chat, repository, context.application)

    await query.answer()
    text = messages.subscription_disabled() if deleted else messages.subscription_not_enabled()
    await _edit_text(query, text, keyboards.build_subscription_keyboard(subscribed=False))


async def lineup_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = await _gate(update, context)
    if query is None or query.message is None:
        return
    chat = query.message.chat
    if chat.type != ChatType.PRIVATE:
        await query.answer(messages.lineup_private_only(), show_alert=True)
        return

    round_ = keyboards.decode_lineup_confirm(query.data or "")
    repository: Repository = context.bot_data["repository"]
    already = confirm_lineup(chat.id, round_, repository, context.application)

    await query.answer()
    text = (
        messages.lineup_already_confirmed(round_) if already else messages.lineup_confirmed(round_)
    )
    await _edit_text(query, text, keyboards.build_lineup_confirmed_keyboard(round_))


async def lineup_undo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = await _gate(update, context)
    if query is None or query.message is None:
        return
    chat = query.message.chat

    round_ = keyboards.decode_lineup_undo(query.data or "")
    repository: Repository = context.bot_data["repository"]
    deleted = undo_lineup_confirmation(chat.id, round_, repository, context.application)

    await query.answer()
    text = (
        messages.lineup_confirmation_cancelled(round_)
        if deleted
        else messages.lineup_not_confirmed()
    )
    await _edit_text(query, text, keyboards.build_lineup_confirm_keyboard(round_))


async def toggle_offset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = await _gate(update, context)
    if query is None or query.message is None:
        return
    chat = query.message.chat
    if not await _may_manage(query, chat, context):
        return

    index, mask = keyboards.decode_toggle(query.data or "")
    await query.answer()
    await _edit_markup(query, keyboards.build_offsets_keyboard(keyboards.toggle_bit(mask, index)))


async def save_offsets_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = await _gate(update, context)
    if query is None or query.message is None:
        return
    chat = query.message.chat
    if not await _may_manage(query, chat, context):
        return

    mask = keyboards.decode_save(query.data or "")
    preset_offsets = keyboards.offsets_from_mask(mask)

    repository: Repository = context.bot_data["repository"]
    existing = repository.get_subscription(chat.id)
    preserved_seconds = (
        keyboards.non_preset_seconds(existing.reminder_offsets) if existing is not None else ()
    )
    merged = tuple(
        sorted({*preset_offsets, *(timedelta(seconds=s) for s in preserved_seconds)}, reverse=True)
    )
    if not merged:
        await query.answer(messages.offsets_selection_empty(), show_alert=True)
        return

    newly_subscribed = set_offsets(chat, merged, repository, context.application)

    await query.answer()
    await _edit_text(
        query,
        messages.offsets_updated(merged, newly_subscribed=newly_subscribed),
        keyboards.build_offsets_keyboard(mask),
    )


async def default_offsets_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = await _gate(update, context)
    if query is None or query.message is None:
        return
    chat = query.message.chat
    if not await _may_manage(query, chat, context):
        return

    settings: Settings = context.bot_data["settings"]
    repository: Repository = context.bot_data["repository"]
    set_offsets(chat, settings.reminder_offsets, repository, context.application)

    mask = keyboards.mask_from_offsets(
        tuple(int(offset.total_seconds()) for offset in settings.reminder_offsets)
    )
    await query.answer()
    await _edit_text(
        query,
        messages.offsets_reset(settings.reminder_offsets),
        keyboards.build_offsets_keyboard(mask),
    )


async def start_custom_offsets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = await _gate(update, context)
    if query is None or query.message is None:
        return None
    chat = query.message.chat
    if not await _may_manage(query, chat, context):
        return None

    mask = keyboards.decode_custom(query.data or "")
    await query.answer()
    await _edit_markup(query, keyboards.build_offsets_waiting_keyboard(mask))

    prompt = await context.bot.send_message(
        chat_id=chat.id,
        text=messages.offsets_custom_prompt(),
        parse_mode=ParseMode.HTML,
        reply_markup=ForceReply(selective=True),
    )
    assert context.user_data is not None
    context.user_data[_GRID_CHAT_ID] = chat.id
    context.user_data[_GRID_MESSAGE_ID] = query.message.message_id
    context.user_data[_GRID_MASK] = mask
    context.user_data[_PROMPT_MESSAGE_ID] = prompt.message_id
    return OFFSETS_CUSTOM_INPUT


async def _restore_grid(context: ContextTypes.DEFAULT_TYPE, *, mask: int) -> None:
    """Rebuilds the grid keyboard on the original message and deletes the prompt."""
    assert context.user_data is not None
    chat_id = context.user_data.pop(_GRID_CHAT_ID, None)
    message_id = context.user_data.pop(_GRID_MESSAGE_ID, None)
    prompt_message_id = context.user_data.pop(_PROMPT_MESSAGE_ID, None)
    context.user_data.pop(_GRID_MASK, None)
    if chat_id is None or message_id is None:
        return
    with contextlib.suppress(BadRequest):
        await context.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=keyboards.build_offsets_keyboard(mask),
        )
    if prompt_message_id is not None:
        with contextlib.suppress(BadRequest):
            await context.bot.delete_message(chat_id=chat_id, message_id=prompt_message_id)


async def _close_custom_offsets(context: ContextTypes.DEFAULT_TYPE) -> None:
    """After a successful custom-offset save, delete the original grid message (and the
    prompt) instead of reopening it: its mask can't represent the just-saved value, so
    leaving it interactive risks a later Salva silently discarding it (ADR 0019)."""
    assert context.user_data is not None
    chat_id = context.user_data.pop(_GRID_CHAT_ID, None)
    message_id = context.user_data.pop(_GRID_MESSAGE_ID, None)
    prompt_message_id = context.user_data.pop(_PROMPT_MESSAGE_ID, None)
    context.user_data.pop(_GRID_MASK, None)
    if chat_id is None:
        return
    if message_id is not None:
        with contextlib.suppress(BadRequest):
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    if prompt_message_id is not None:
        with contextlib.suppress(BadRequest):
            await context.bot.delete_message(chat_id=chat_id, message_id=prompt_message_id)


async def receive_custom_offsets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    if message is None or message.text is None or update.effective_chat is None:
        return OFFSETS_CUSTOM_INPUT
    chat = update.effective_chat

    try:
        offsets = parse_offsets_args(message.text.split())
    except OffsetsParseError as exc:
        await message.reply_text(
            OFFSETS_ERROR_MESSAGES[exc.reason](exc.token), parse_mode=ParseMode.HTML
        )
        return OFFSETS_CUSTOM_INPUT

    repository: Repository = context.bot_data["repository"]
    newly_subscribed = set_offsets(chat, offsets, repository, context.application)
    await message.reply_text(
        messages.offsets_updated(offsets, newly_subscribed=newly_subscribed),
        parse_mode=ParseMode.HTML,
    )

    await _close_custom_offsets(context)
    return ConversationHandler.END


async def cancel_custom_offsets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert context.user_data is not None
    mask = context.user_data.get(_GRID_MASK, 0)
    await _restore_grid(context, mask=mask)
    if update.message is not None:
        await update.message.reply_text(
            messages.offsets_custom_cancelled(), parse_mode=ParseMode.HTML
        )
    return ConversationHandler.END


async def back_from_custom_offsets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    mask = keyboards.decode_back(query.data or "")
    await query.answer()
    await _restore_grid(context, mask=mask)
    return ConversationHandler.END


async def timeout_custom_offsets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert context.user_data is not None
    chat_id = context.user_data.get(_GRID_CHAT_ID)
    mask = context.user_data.get(_GRID_MASK, 0)
    await _restore_grid(context, mask=mask)
    if chat_id is not None:
        await context.bot.send_message(
            chat_id=chat_id, text=messages.offsets_custom_timeout(), parse_mode=ParseMode.HTML
        )


custom_offsets_conversation = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(
            start_custom_offsets, pattern=rf"^{re.escape(keyboards.CB_CUSTOM_PREFIX)}"
        )
    ],
    states={
        OFFSETS_CUSTOM_INPUT: [
            CallbackQueryHandler(
                back_from_custom_offsets, pattern=rf"^{re.escape(keyboards.CB_BACK_PREFIX)}"
            ),
            CommandHandler("annulla", cancel_custom_offsets),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_offsets),
        ],
        ConversationHandler.TIMEOUT: [
            MessageHandler(filters.ALL, timeout_custom_offsets),
        ],
    },
    fallbacks=[CommandHandler("annulla", cancel_custom_offsets)],
    conversation_timeout=300,
)


def register(application: BotApp) -> None:
    """Registers all callback/conversation handlers on the application.

    Callback queries ignore PTB's chat filters (they only apply to Message-based
    handlers), so the ALLOWED_CHAT_IDS gate is re-checked inside _gate instead of
    passed in here.
    """
    application.add_handler(
        CallbackQueryHandler(subscribe_callback, pattern=rf"^{re.escape(keyboards.CB_SUBSCRIBE)}$")
    )
    application.add_handler(
        CallbackQueryHandler(
            unsubscribe_callback, pattern=rf"^{re.escape(keyboards.CB_UNSUBSCRIBE)}$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            toggle_offset_callback, pattern=rf"^{re.escape(keyboards.CB_TOGGLE_PREFIX)}"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            save_offsets_callback, pattern=rf"^{re.escape(keyboards.CB_SAVE_PREFIX)}"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            default_offsets_callback, pattern=rf"^{re.escape(keyboards.CB_OFFSETS_DEFAULT)}$"
        )
    )
    application.add_handler(custom_offsets_conversation)
    application.add_handler(
        CallbackQueryHandler(
            lineup_confirm_callback, pattern=rf"^{re.escape(keyboards.CB_LINEUP_CONFIRM_PREFIX)}"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            lineup_undo_callback, pattern=rf"^{re.escape(keyboards.CB_LINEUP_UNDO_PREFIX)}"
        )
    )
