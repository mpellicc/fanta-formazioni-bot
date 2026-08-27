import pytest
from telegram.error import BadRequest, Forbidden, NetworkError, TimedOut

from fantaformazionibot.telegram.errors import (
    is_dead_chat_error,
    is_unwritable_chat_error,
)


@pytest.mark.parametrize(
    "error",
    [
        BadRequest("Topic_closed"),
        BadRequest("Message thread not found"),
        BadRequest("Chat not found"),
        Forbidden("Bot was kicked from the supergroup chat"),
        Forbidden("Bot was blocked by the user"),
    ],
)
def test_unwritable_chat_errors_are_not_reported(error: Exception) -> None:
    assert is_unwritable_chat_error(error)


@pytest.mark.parametrize(
    "error",
    [
        BadRequest("Can't parse entities: unsupported start tag"),
        BadRequest("Message is too long"),
        NetworkError("httpx.ReadError"),
        TimedOut(),
        ValueError("a plain handler bug"),
        None,
    ],
)
def test_actionable_errors_are_still_reported(error: Exception | None) -> None:
    assert not is_unwritable_chat_error(error)


@pytest.mark.parametrize(
    "error",
    [
        Forbidden("Bot was blocked by the user"),
        Forbidden("Bot was kicked from the supergroup chat"),
        Forbidden("Bot is not a member of the channel chat"),
        Forbidden("User is deactivated"),
        BadRequest("Chat not found"),
    ],
)
def test_dead_chat_errors_prune_the_subscription(error: Exception) -> None:
    assert is_dead_chat_error(error)


@pytest.mark.parametrize(
    "error",
    [
        BadRequest("Topic_closed"),
        BadRequest("Message thread not found"),
        BadRequest("Can't parse entities: unsupported start tag"),
        NetworkError("httpx.ReadError"),
        None,
    ],
)
def test_transient_errors_do_not_prune_the_subscription(error: Exception | None) -> None:
    assert not is_dead_chat_error(error)


def test_every_dead_chat_error_is_also_unwritable() -> None:
    for error in (Forbidden("Bot was blocked by the user"), BadRequest("Chat not found")):
        assert is_dead_chat_error(error)
        assert is_unwritable_chat_error(error)
