"""Inline keyboard builders and callback_data codec for reminder buttons (ADR 0015).

Preset selection state travels entirely inside callback_data (an 8-bit mask
over OFFSET_PRESETS) so keyboards stay stateless across bot restarts.
"""

from collections.abc import Sequence
from datetime import timedelta
from typing import Literal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from fantaformazionibot import format as fmt

# Button label wording (single source of truth: messages.py imports these for any
# prose that names a button, so the two never drift independently — ADR 0018 §10).
ACTION_SUBSCRIBE = "Attiva promemoria"
ACTION_UNSUBSCRIBE = "Disattiva promemoria"
ACTION_SAVE = "Salva"
ACTION_DEFAULTS = "Predefiniti"
ACTION_CUSTOM = "Personalizzati"
ACTION_BACK = "Indietro"
ACTION_LINEUP_CONFIRM = "Ho schierato"
ACTION_LINEUP_UNDO = "Annulla conferma"
ACTION_ROSTER_JOIN = "Sono un manager"
ACTION_ROSTER_CLOSE = "Chiudi iscrizioni"
ACTION_ROSTER_REOPEN = "Riapri iscrizioni"
ACTION_TOPIC_BIND = "Manda in questo topic"
ACTION_TOPIC_UNBIND = "Riporta in chat principale"
ACTION_ADD_TO_GROUP = "Aggiungimi a un gruppo"

OFFSET_PRESETS: tuple[timedelta, ...] = (
    timedelta(days=2),
    timedelta(hours=24),
    timedelta(hours=12),
    timedelta(hours=3),
    timedelta(hours=1),
    timedelta(minutes=30),
    timedelta(minutes=10),
    timedelta(minutes=5),
)

CB_SUBSCRIBE = "sub:on"
CB_UNSUBSCRIBE = "sub:off"
CB_OFFSETS_DEFAULT = "off:default"
CB_TOGGLE_PREFIX = "off:t:"
CB_SAVE_PREFIX = "off:save:"
CB_CUSTOM_PREFIX = "off:custom:"
CB_BACK_PREFIX = "off:back:"
CB_LINEUP_CONFIRM_PREFIX = "lineup:confirm:"
CB_LINEUP_UNDO_PREFIX = "lineup:undo:"
# Group roster and per-user lineup confirmations (ADR 0027). The confirmed/total counter
# lives in the button label, never in callback_data: the payload stays a bare round, so
# a stale keyboard can't feed a wrong count back to the handler.
CB_GROUP_CONFIRM_PREFIX = "glineup:confirm:"
CB_GROUP_UNDO_PREFIX = "glineup:undo:"
CB_ROSTER_JOIN = "roster:join"
CB_ROSTER_CLOSE = "roster:close"
CB_ROSTER_REOPEN = "roster:reopen"
# Forum-topic destination (ADR 0031). Deliberately payload-free: the target topic is
# re-read from the pressed message, which *is* the topic the button lives in, so a
# stale keyboard can never deliver to a topic other than the one it is visible in.
CB_TOPIC_BIND = "sub:topic:on"
CB_TOPIC_UNBIND = "sub:topic:off"


def _decode_masked(prefix: str, data: str) -> int:
    """Raises ValueError if data doesn't start with prefix."""
    if not data.startswith(prefix):
        raise ValueError(f"expected prefix {prefix!r}: {data!r}")
    return int(data.removeprefix(prefix))


def mask_from_offsets(offsets_seconds: Sequence[int]) -> int:
    """Bitmask of OFFSET_PRESETS present in offsets_seconds; non-preset values are ignored."""
    seconds_set = set(offsets_seconds)
    mask = 0
    for index, preset in enumerate(OFFSET_PRESETS):
        if int(preset.total_seconds()) in seconds_set:
            mask |= 1 << index
    return mask


def offsets_from_mask(mask: int) -> tuple[timedelta, ...]:
    return tuple(preset for index, preset in enumerate(OFFSET_PRESETS) if mask & (1 << index))


def non_preset_seconds(offsets_seconds: Sequence[int]) -> tuple[int, ...]:
    """Offsets (seconds) in offsets_seconds that aren't one of OFFSET_PRESETS.

    Used to preserve free-form custom offsets across a grid Salva, which can
    only represent presets (ADR 0020).
    """
    preset_seconds = {int(preset.total_seconds()) for preset in OFFSET_PRESETS}
    return tuple(seconds for seconds in offsets_seconds if seconds not in preset_seconds)


def toggle_bit(mask: int, index: int) -> int:
    return mask ^ (1 << index)


def encode_toggle(index: int, mask: int) -> str:
    return f"{CB_TOGGLE_PREFIX}{index}:{mask}"


def decode_toggle(data: str) -> tuple[int, int]:
    """Returns (index, mask). Raises ValueError if data isn't a toggle callback."""
    if not data.startswith(CB_TOGGLE_PREFIX):
        raise ValueError(f"not a toggle callback: {data!r}")
    index_str, mask_str = data.removeprefix(CB_TOGGLE_PREFIX).split(":")
    return int(index_str), int(mask_str)


def encode_save(mask: int) -> str:
    return f"{CB_SAVE_PREFIX}{mask}"


def decode_save(data: str) -> int:
    return _decode_masked(CB_SAVE_PREFIX, data)


def encode_custom(mask: int) -> str:
    return f"{CB_CUSTOM_PREFIX}{mask}"


def decode_custom(data: str) -> int:
    return _decode_masked(CB_CUSTOM_PREFIX, data)


def encode_back(mask: int) -> str:
    return f"{CB_BACK_PREFIX}{mask}"


def decode_back(data: str) -> int:
    return _decode_masked(CB_BACK_PREFIX, data)


TopicAction = Literal["bind", "unbind"]


def topic_action(
    *,
    is_forum: bool,
    subscribed: bool,
    current_thread_id: int | None,
    bound_thread_id: int | None,
) -> TopicAction | None:
    """Which destination button /promemoria should offer, if any (ADR 0031).

    Pure, like planner.py: the callers read Chat.is_forum and the two thread ids,
    this decides. When not subscribed there is nothing to offer — the visible
    "Attiva promemoria" already binds the topic it is pressed in (ADR 0025).
    """
    if not is_forum or not subscribed:
        return None
    if current_thread_id is not None and current_thread_id != bound_thread_id:
        return "bind"
    # Either we are standing in the bound topic, or in "General" (thread id None)
    # while delivery is pinned elsewhere: both times the useful move is to unpin.
    if bound_thread_id is not None:
        return "unbind"
    return None


def build_subscription_keyboard(
    *, subscribed: bool, topic: TopicAction | None = None
) -> InlineKeyboardMarkup:
    button = (
        InlineKeyboardButton(f"🔕 {ACTION_UNSUBSCRIBE}", callback_data=CB_UNSUBSCRIBE)
        if subscribed
        else InlineKeyboardButton(f"🔔 {ACTION_SUBSCRIBE}", callback_data=CB_SUBSCRIBE)
    )
    rows = [[button]]
    if topic == "bind":
        rows.append([InlineKeyboardButton(f"📌 {ACTION_TOPIC_BIND}", callback_data=CB_TOPIC_BIND)])
    elif topic == "unbind":
        rows.append(
            [InlineKeyboardButton(f"📌 {ACTION_TOPIC_UNBIND}", callback_data=CB_TOPIC_UNBIND)]
        )
    return InlineKeyboardMarkup(rows)


def build_start_keyboard(*, subscribed: bool, bot_username: str | None) -> InlineKeyboardMarkup:
    """/start's keyboard: the subscription toggle plus, in private chats, the share
    button (ADR 0032).

    bot_username is None wherever the share button makes no sense — in a group the
    bot is already in, there is nothing to add it to. The button is a plain url:
    it opens Telegram's own group picker and produces no callback of its own.
    """
    rows: list[list[InlineKeyboardButton]] = [
        list(row) for row in build_subscription_keyboard(subscribed=subscribed).inline_keyboard
    ]
    if bot_username is not None:
        rows.append(
            [
                InlineKeyboardButton(
                    f"👥 {ACTION_ADD_TO_GROUP}",
                    url=f"https://t.me/{bot_username}?startgroup=true",
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


def build_offsets_keyboard(mask: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for start in range(0, len(OFFSET_PRESETS), 2):
        row = []
        for index in (start, start + 1):
            if index >= len(OFFSET_PRESETS):
                continue
            preset = OFFSET_PRESETS[index]
            checked = "✓ " if mask & (1 << index) else ""
            row.append(
                InlineKeyboardButton(
                    f"{checked}{fmt.format_duration(preset)}",
                    callback_data=encode_toggle(index, mask),
                )
            )
        rows.append(row)
    rows.append(
        [
            InlineKeyboardButton(f"💾 {ACTION_SAVE}", callback_data=encode_save(mask)),
            InlineKeyboardButton(f"↩️ {ACTION_DEFAULTS}", callback_data=CB_OFFSETS_DEFAULT),
        ]
    )
    rows.append([InlineKeyboardButton(f"✏️ {ACTION_CUSTOM}", callback_data=encode_custom(mask))])
    return InlineKeyboardMarkup(rows)


def build_offsets_waiting_keyboard(mask: int) -> InlineKeyboardMarkup:
    button = InlineKeyboardButton(f"⬅️ {ACTION_BACK}", callback_data=encode_back(mask))
    return InlineKeyboardMarkup([[button]])


def encode_lineup_confirm(round_: int) -> str:
    return f"{CB_LINEUP_CONFIRM_PREFIX}{round_}"


def decode_lineup_confirm(data: str) -> int:
    return _decode_masked(CB_LINEUP_CONFIRM_PREFIX, data)


def encode_lineup_undo(round_: int) -> str:
    return f"{CB_LINEUP_UNDO_PREFIX}{round_}"


def decode_lineup_undo(data: str) -> int:
    return _decode_masked(CB_LINEUP_UNDO_PREFIX, data)


def build_lineup_confirm_keyboard(round_: int) -> InlineKeyboardMarkup:
    button = InlineKeyboardButton(
        f"✅ {ACTION_LINEUP_CONFIRM}", callback_data=encode_lineup_confirm(round_)
    )
    return InlineKeyboardMarkup([[button]])


def build_lineup_confirmed_keyboard(round_: int) -> InlineKeyboardMarkup:
    button = InlineKeyboardButton(
        f"↩️ {ACTION_LINEUP_UNDO}", callback_data=encode_lineup_undo(round_)
    )
    return InlineKeyboardMarkup([[button]])


def encode_group_confirm(round_: int) -> str:
    return f"{CB_GROUP_CONFIRM_PREFIX}{round_}"


def decode_group_confirm(data: str) -> int:
    return _decode_masked(CB_GROUP_CONFIRM_PREFIX, data)


def encode_group_undo(round_: int) -> str:
    return f"{CB_GROUP_UNDO_PREFIX}{round_}"


def decode_group_undo(data: str) -> int:
    return _decode_masked(CB_GROUP_UNDO_PREFIX, data)


def build_group_lineup_keyboard(round_: int, confirmed: int, total: int) -> InlineKeyboardMarkup:
    """Reminder keyboard for groups (ADR 0027).

    One keyboard is shared by every member, so it can't reflect who already confirmed:
    both buttons are always shown and each acts on the presser alone.
    """
    # One button per row: side by side, Telegram truncates the labels and the counter
    # — the whole point of the group variant — is the first thing to go.
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"✅ {ACTION_LINEUP_CONFIRM} ({confirmed}/{total})",
                    callback_data=encode_group_confirm(round_),
                )
            ],
            [
                InlineKeyboardButton(
                    f"↩️ {ACTION_LINEUP_UNDO}", callback_data=encode_group_undo(round_)
                )
            ],
        ]
    )


def build_roster_keyboard(*, closed: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if not closed:
        rows.append(
            [InlineKeyboardButton(f"🙋 {ACTION_ROSTER_JOIN}", callback_data=CB_ROSTER_JOIN)]
        )
        rows.append(
            [InlineKeyboardButton(f"🔒 {ACTION_ROSTER_CLOSE}", callback_data=CB_ROSTER_CLOSE)]
        )
    else:
        rows.append(
            [InlineKeyboardButton(f"🔓 {ACTION_ROSTER_REOPEN}", callback_data=CB_ROSTER_REOPEN)]
        )
    return InlineKeyboardMarkup(rows)
