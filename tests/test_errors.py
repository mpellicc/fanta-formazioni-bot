import pytest
from telegram.error import BadRequest, Forbidden, NetworkError, TimedOut

from fantaformazionibot.telegram.errors import is_unwritable_chat_error


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
