"""Inline keyboard builders and callback_data codec for reminder buttons (ADR 0015).

Preset selection state travels entirely inside callback_data (an 8-bit mask
over OFFSET_PRESETS) so keyboards stay stateless across bot restarts.
"""

from collections.abc import Sequence
from datetime import timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from fantaformazionibot import format as fmt

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


def build_subscription_keyboard(*, subscribed: bool) -> InlineKeyboardMarkup:
    button = (
        InlineKeyboardButton("🔕 Disattiva promemoria", callback_data=CB_UNSUBSCRIBE)
        if subscribed
        else InlineKeyboardButton("🔔 Attiva promemoria", callback_data=CB_SUBSCRIBE)
    )
    return InlineKeyboardMarkup([[button]])


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
            InlineKeyboardButton("💾 Salva", callback_data=encode_save(mask)),
            InlineKeyboardButton("↩️ Predefiniti", callback_data=CB_OFFSETS_DEFAULT),
        ]
    )
    rows.append([InlineKeyboardButton("✏️ Personalizzati", callback_data=encode_custom(mask))])
    return InlineKeyboardMarkup(rows)


def build_offsets_waiting_keyboard(mask: int) -> InlineKeyboardMarkup:
    button = InlineKeyboardButton("⬅️ Indietro", callback_data=encode_back(mask))
    return InlineKeyboardMarkup([[button]])
