from datetime import UTC, datetime, timedelta

import pytest
from telegram import Chat, Message

from fantaformazionibot.telegram.commands import (
    OffsetsParseError,
    is_addressed_to_other_bot,
    parse_offsets_args,
    topic_thread_id,
)

_CHAT = Chat(id=1, type="supergroup")


def _message(*, is_topic_message: bool | None, message_thread_id: int | None) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=_CHAT,
        is_topic_message=is_topic_message,
        message_thread_id=message_thread_id,
    )


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


@pytest.mark.parametrize(
    "text",
    ["/list@rss2tg_bot", "/list@RSS2TG_Bot", "/list@other_bot argomento"],
)
def test_is_addressed_to_other_bot(text: str) -> None:
    assert is_addressed_to_other_bot(text, "FantaFormazioniBot")


@pytest.mark.parametrize(
    "text",
    [
        "/list",
        "/list argomento",
        "/list@FantaFormazioniBot",
        "/list@fantaformazionibot",
        "/LIST@FANTAFORMAZIONIBOT",
        "",
    ],
)
def test_is_not_addressed_to_other_bot(text: str) -> None:
    assert not is_addressed_to_other_bot(text, "FantaFormazioniBot")


def test_topic_thread_id_none_message() -> None:
    assert topic_thread_id(None) is None


def test_topic_thread_id_non_forum_chat() -> None:
    message = _message(is_topic_message=None, message_thread_id=None)
    assert topic_thread_id(message) is None


def test_topic_thread_id_general_topic() -> None:
    message = _message(is_topic_message=False, message_thread_id=None)
    assert topic_thread_id(message) is None


def test_topic_thread_id_real_topic() -> None:
    message = _message(is_topic_message=True, message_thread_id=99)
    assert topic_thread_id(message) == 99
