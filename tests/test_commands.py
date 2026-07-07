from datetime import timedelta

import pytest

from fantaformazionibot.telegram.commands import OffsetsParseError, parse_offsets_args


def test_parse_offsets_args_space_separated() -> None:
    assert parse_offsets_args(["24h", "1h", "5m"]) == (
        timedelta(hours=24),
        timedelta(hours=1),
        timedelta(minutes=5),
    )


def test_parse_offsets_args_comma_separated() -> None:
    assert parse_offsets_args(["24h,1h,5m"]) == (
        timedelta(hours=24),
        timedelta(hours=1),
        timedelta(minutes=5),
    )


def test_parse_offsets_args_mixed_spaces_and_commas() -> None:
    assert parse_offsets_args(["24h,", "1h", ",5m"]) == (
        timedelta(hours=24),
        timedelta(hours=1),
        timedelta(minutes=5),
    )


def test_parse_offsets_args_dedupes() -> None:
    assert parse_offsets_args(["1h", "1h", "60m"]) == (timedelta(hours=1),)


def test_parse_offsets_args_sorts_descending() -> None:
    assert parse_offsets_args(["5m", "24h", "1h"]) == (
        timedelta(hours=24),
        timedelta(hours=1),
        timedelta(minutes=5),
    )


def test_parse_offsets_args_empty_raises() -> None:
    with pytest.raises(OffsetsParseError) as exc_info:
        parse_offsets_args([])
    assert exc_info.value.reason == "empty"


def test_parse_offsets_args_too_many_raises() -> None:
    with pytest.raises(OffsetsParseError) as exc_info:
        parse_offsets_args([f"{n}m" for n in range(1, 12)])
    assert exc_info.value.reason == "too_many"


def test_parse_offsets_args_invalid_token_raises() -> None:
    with pytest.raises(OffsetsParseError) as exc_info:
        parse_offsets_args(["banana"])
    assert exc_info.value.reason == "invalid_token"
    assert exc_info.value.token == "banana"


@pytest.mark.parametrize("token", ["30s", "10081m"])
def test_parse_offsets_args_out_of_range_raises(token: str) -> None:
    with pytest.raises(OffsetsParseError) as exc_info:
        parse_offsets_args([token])
    assert exc_info.value.reason == "out_of_range"
    assert exc_info.value.token == token
