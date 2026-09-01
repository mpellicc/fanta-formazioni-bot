from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from telegram import Chat, Message

from fantaformazionibot.storage.repository import Repository
from fantaformazionibot.telegram import commands
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


def _group_repository(tmp_path: Path) -> Repository:
    return Repository(tmp_path / "test.db")


def test_confirm_group_lineup_silences_only_when_everyone_confirmed(tmp_path: Path) -> None:
    repository = _group_repository(tmp_path)
    application = MagicMock()
    repository.add_group_participant(-100, 1)
    repository.add_group_participant(-100, 2)
    repository.close_roster(-100)

    first = commands.confirm_group_lineup(-100, 7, 1, repository, application)
    assert (first.confirmed, first.total, first.complete) == (1, 2, False)
    assert repository.is_lineup_confirmed(-100, 7) is False

    second = commands.confirm_group_lineup(-100, 7, 2, repository, application)
    assert second.complete is True
    assert repository.is_lineup_confirmed(-100, 7) is True


def test_undo_group_lineup_confirmation_resumes_reminders(tmp_path: Path) -> None:
    repository = _group_repository(tmp_path)
    application = MagicMock()
    repository.add_group_participant(-100, 1)
    repository.close_roster(-100)
    commands.confirm_group_lineup(-100, 7, 1, repository, application)

    result = commands.undo_group_lineup_confirmation(-100, 7, 1, repository, application)

    assert result.already is False
    assert repository.is_lineup_confirmed(-100, 7) is False


def test_confirm_group_lineup_enrols_the_presser_while_enrollment_is_open(
    tmp_path: Path,
) -> None:
    repository = _group_repository(tmp_path)

    result = commands.confirm_group_lineup(-100, 7, 1, repository, MagicMock())

    assert (result.confirmed, result.total) == (1, 1)
    assert repository.get_group_participants(-100) == [1]


def test_join_roster_unmutes_a_chat_that_had_already_confirmed(tmp_path: Path) -> None:
    """A newcomer invalidates a lazy "everyone confirmed" (ADR 0027)."""
    repository = _group_repository(tmp_path)
    application = MagicMock()
    commands.confirm_group_lineup(-100, 7, 1, repository, application)
    assert repository.is_lineup_confirmed(-100, 7) is True

    assert commands.join_roster(-100, 2, repository, application) is True

    assert repository.is_lineup_confirmed(-100, 7) is False


def test_join_roster_is_a_no_op_once_enrollment_is_closed(tmp_path: Path) -> None:
    repository = _group_repository(tmp_path)
    repository.close_roster(-100)

    assert commands.join_roster(-100, 1, repository, MagicMock()) is False
    assert repository.count_group_participants(-100) == 0


def test_reset_group_roster_clears_roster_and_silencing(tmp_path: Path) -> None:
    repository = _group_repository(tmp_path)
    application = MagicMock()
    commands.confirm_group_lineup(-100, 7, 1, repository, application)
    repository.close_roster(-100)

    commands.reset_group_roster(-100, repository, application)

    assert repository.count_group_participants(-100) == 0
    assert repository.is_lineup_confirmed(-100, 7) is False
    assert repository.is_roster_closed(-100) is False
