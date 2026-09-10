from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from telegram import Chat, Message

from fantaformazionibot.models import Subscription
from fantaformazionibot.storage.repository import Repository
from fantaformazionibot.telegram import commands, keyboards
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


def _forum_chat(*, is_forum: bool = True) -> Chat:
    return Chat(id=-100, type="supergroup", is_forum=is_forum)


def _subscribe(repository: Repository, thread_id: int | None) -> None:
    repository.upsert_subscription(
        Subscription(
            chat_id=-100,
            chat_type="supergroup",
            reminder_offsets=(3600,),
            origin="user",
            message_thread_id=thread_id,
        )
    )


def test_rebind_topic_moves_delivery_to_the_given_topic(tmp_path: Path) -> None:
    repository = _group_repository(tmp_path)
    _subscribe(repository, None)

    result = commands.rebind_topic(_forum_chat(), 42, repository)

    assert result == commands.RebindResult(subscribed=True, topic_changed=True)
    subscription = repository.get_subscription(-100)
    assert subscription is not None
    assert subscription.message_thread_id == 42


def test_rebind_topic_unpins_when_given_none(tmp_path: Path) -> None:
    repository = _group_repository(tmp_path)
    _subscribe(repository, 42)

    result = commands.rebind_topic(_forum_chat(), None, repository)

    assert result.topic_changed is True
    subscription = repository.get_subscription(-100)
    assert subscription is not None
    assert subscription.message_thread_id is None


def test_rebind_topic_to_the_same_topic_changes_nothing(tmp_path: Path) -> None:
    repository = _group_repository(tmp_path)
    _subscribe(repository, 42)

    assert commands.rebind_topic(_forum_chat(), 42, repository) == commands.RebindResult(
        subscribed=True, topic_changed=False
    )


def test_rebind_topic_never_creates_a_subscription(tmp_path: Path) -> None:
    """A stale keyboard pressed after /promemoria off must not resurrect the chat."""
    repository = _group_repository(tmp_path)

    result = commands.rebind_topic(_forum_chat(), 42, repository)

    assert result == commands.RebindResult(subscribed=False, topic_changed=False)
    assert repository.get_subscription(-100) is None


def test_rebind_topic_leaves_offsets_alone(tmp_path: Path) -> None:
    repository = _group_repository(tmp_path)
    _subscribe(repository, None)

    commands.rebind_topic(_forum_chat(), 42, repository)

    subscription = repository.get_subscription(-100)
    assert subscription is not None
    assert subscription.reminder_offsets == (3600,)


def test_subscription_status_view_offers_the_move_from_another_topic(tmp_path: Path) -> None:
    repository = _group_repository(tmp_path)
    _subscribe(repository, None)

    text, markup = commands.subscription_status_view(
        _forum_chat(), repository.get_subscription(-100), 42
    )

    assert "chat principale" in text
    assert markup.inline_keyboard[1][0].callback_data == keyboards.CB_TOPIC_BIND


def test_subscription_status_view_offers_the_undo_from_the_bound_topic(tmp_path: Path) -> None:
    repository = _group_repository(tmp_path)
    _subscribe(repository, 42)

    text, markup = commands.subscription_status_view(
        _forum_chat(), repository.get_subscription(-100), 42
    )

    assert "in questo topic" in text
    assert markup.inline_keyboard[1][0].callback_data == keyboards.CB_TOPIC_UNBIND


def test_subscription_status_view_names_no_topic_when_bound_elsewhere(tmp_path: Path) -> None:
    repository = _group_repository(tmp_path)
    _subscribe(repository, 99)

    text, _ = commands.subscription_status_view(
        _forum_chat(), repository.get_subscription(-100), 42
    )

    assert "un altro topic" in text


def test_subscription_status_view_is_unchanged_outside_forums(tmp_path: Path) -> None:
    """Plain groups have no topics: their status text must stay byte-identical."""
    repository = _group_repository(tmp_path)
    _subscribe(repository, None)
    subscription = repository.get_subscription(-100)

    text, markup = commands.subscription_status_view(
        _forum_chat(is_forum=False), subscription, None
    )

    assert "📌" not in text
    assert len(markup.inline_keyboard) == 1


def test_subscription_status_view_without_subscription_offers_only_activation() -> None:
    text, markup = commands.subscription_status_view(_forum_chat(), None, 42)

    assert "📌" not in text
    assert [button.callback_data for row in markup.inline_keyboard for button in row] == [
        keyboards.CB_SUBSCRIBE
    ]


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ([], None),
        ([""], None),
        (["canale"], "canale"),
        (["gruppo-x_1"], "gruppo-x_1"),
        (["A" * 32], "A" * 32),
    ],
)
def test_parse_start_payload_accepts_slugs(args: list[str], expected: str | None) -> None:
    assert commands.parse_start_payload(args) == expected


@pytest.mark.parametrize(
    "payload",
    [
        "con spazio",
        "chat_id=1",
        "a" * 33,
        "sorgente!",
        "riga\nspezzata",
    ],
)
def test_parse_start_payload_rejects_anything_that_would_break_the_log_line(
    payload: str,
) -> None:
    """The payload is attacker-controllable and lands in `source=` of a line the
    dashboard parses by key (ADR 0028 §2): the original is never echoed back."""
    assert commands.parse_start_payload([payload]) == commands.INVALID_START_PAYLOAD
