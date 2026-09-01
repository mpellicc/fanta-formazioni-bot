from datetime import timedelta

import pytest

from fantaformazionibot.telegram import keyboards


def test_mask_from_offsets_matches_presets() -> None:
    picked = (timedelta(hours=24), timedelta(minutes=5))
    seconds = tuple(int(offset.total_seconds()) for offset in picked)
    mask = keyboards.mask_from_offsets(seconds)
    assert keyboards.offsets_from_mask(mask) == picked


def test_mask_from_offsets_ignores_non_preset_values() -> None:
    seconds = (int(timedelta(hours=24).total_seconds()), 123)
    mask = keyboards.mask_from_offsets(seconds)
    assert keyboards.offsets_from_mask(mask) == (timedelta(hours=24),)


def test_non_preset_seconds_filters_out_presets() -> None:
    preset_seconds = int(timedelta(hours=24).total_seconds())
    custom_seconds = int(timedelta(minutes=90).total_seconds())
    result = keyboards.non_preset_seconds((preset_seconds, custom_seconds))
    assert result == (custom_seconds,)


def test_non_preset_seconds_empty_when_all_presets() -> None:
    preset_seconds = tuple(int(preset.total_seconds()) for preset in keyboards.OFFSET_PRESETS)
    assert keyboards.non_preset_seconds(preset_seconds) == ()


def test_offsets_from_mask_empty() -> None:
    assert keyboards.offsets_from_mask(0) == ()


def test_offsets_from_mask_all_presets() -> None:
    full_mask = (1 << len(keyboards.OFFSET_PRESETS)) - 1
    assert keyboards.offsets_from_mask(full_mask) == keyboards.OFFSET_PRESETS


def test_toggle_bit_flips_and_is_its_own_inverse() -> None:
    mask = keyboards.toggle_bit(0, 3)
    assert mask == 0b1000
    assert keyboards.toggle_bit(mask, 3) == 0


@pytest.mark.parametrize(
    ("encode", "decode", "value"),
    [
        (keyboards.encode_save, keyboards.decode_save, 5),
        (keyboards.encode_custom, keyboards.decode_custom, 5),
        (keyboards.encode_back, keyboards.decode_back, 5),
        (keyboards.encode_lineup_confirm, keyboards.decode_lineup_confirm, 7),
        (keyboards.encode_lineup_undo, keyboards.decode_lineup_undo, 7),
    ],
)
def test_masked_callback_data_roundtrips(encode: object, decode: object, value: int) -> None:
    data = encode(value)  # type: ignore[operator]
    assert decode(data) == value  # type: ignore[operator]


def test_encode_decode_toggle_roundtrips() -> None:
    data = keyboards.encode_toggle(3, 0b0101)
    assert keyboards.decode_toggle(data) == (3, 0b0101)


def test_decode_toggle_rejects_other_prefixes() -> None:
    with pytest.raises(ValueError):
        keyboards.decode_toggle(keyboards.encode_save(1))


def test_decode_save_rejects_other_prefixes() -> None:
    with pytest.raises(ValueError):
        keyboards.decode_save(keyboards.CB_SUBSCRIBE)


def test_decode_lineup_confirm_rejects_other_prefixes() -> None:
    with pytest.raises(ValueError):
        keyboards.decode_lineup_confirm(keyboards.encode_lineup_undo(7))


def test_decode_lineup_undo_rejects_other_prefixes() -> None:
    with pytest.raises(ValueError):
        keyboards.decode_lineup_undo(keyboards.encode_lineup_confirm(7))


def test_build_offsets_keyboard_marks_checked_presets() -> None:
    mask = keyboards.mask_from_offsets((int(keyboards.OFFSET_PRESETS[0].total_seconds()),))
    markup = keyboards.build_offsets_keyboard(mask)
    buttons = [button for row in markup.inline_keyboard for button in row]
    checked = [button for button in buttons if button.text.startswith("✓")]
    assert len(checked) == 1


def test_build_subscription_keyboard_reflects_state() -> None:
    subscribed = keyboards.build_subscription_keyboard(subscribed=True)
    not_subscribed = keyboards.build_subscription_keyboard(subscribed=False)
    assert subscribed.inline_keyboard[0][0].callback_data == keyboards.CB_UNSUBSCRIBE
    assert not_subscribed.inline_keyboard[0][0].callback_data == keyboards.CB_SUBSCRIBE


def test_build_lineup_confirm_keyboard_encodes_round() -> None:
    markup = keyboards.build_lineup_confirm_keyboard(7)
    button = markup.inline_keyboard[0][0]
    assert button.callback_data == keyboards.encode_lineup_confirm(7)


def test_build_lineup_confirmed_keyboard_encodes_round() -> None:
    markup = keyboards.build_lineup_confirmed_keyboard(7)
    button = markup.inline_keyboard[0][0]
    assert button.callback_data == keyboards.encode_lineup_undo(7)


def test_group_confirm_roundtrip() -> None:
    assert keyboards.decode_group_confirm(keyboards.encode_group_confirm(7)) == 7


def test_group_undo_roundtrip() -> None:
    assert keyboards.decode_group_undo(keyboards.encode_group_undo(7)) == 7


def test_decode_group_confirm_rejects_other_prefixes() -> None:
    with pytest.raises(ValueError):
        keyboards.decode_group_confirm(keyboards.encode_lineup_confirm(7))


def test_decode_group_undo_rejects_other_prefixes() -> None:
    with pytest.raises(ValueError):
        keyboards.decode_group_undo(keyboards.encode_group_confirm(7))


def test_build_group_lineup_keyboard_shows_counter_and_both_actions() -> None:
    markup = keyboards.build_group_lineup_keyboard(7, 3, 5)
    confirm, undo = markup.inline_keyboard[0]
    assert "(3/5)" in confirm.text
    assert confirm.callback_data == keyboards.encode_group_confirm(7)
    assert undo.callback_data == keyboards.encode_group_undo(7)


def test_build_roster_keyboard_open_offers_join_and_close() -> None:
    markup = keyboards.build_roster_keyboard(closed=False)
    data = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert data == [keyboards.CB_ROSTER_JOIN, keyboards.CB_ROSTER_CLOSE]


def test_build_roster_keyboard_closed_offers_only_reopen() -> None:
    markup = keyboards.build_roster_keyboard(closed=True)
    data = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert data == [keyboards.CB_ROSTER_REOPEN]
