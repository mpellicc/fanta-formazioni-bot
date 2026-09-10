import pytest

from fantaformazionibot.telegram import messages
from fantaformazionibot.telegram.inline import (
    RESULT_DEADLINE,
    RESULT_INVITE,
    build_results,
    inline_allowed,
)


def test_inline_allowed_is_open_when_the_whitelist_is_empty() -> None:
    """Empty means open, exactly like allowed_chat_ids: that is production."""
    assert inline_allowed(7, ()) is True


def test_inline_allowed_accepts_a_whitelisted_user() -> None:
    assert inline_allowed(7, (7, 9)) is True


def test_inline_allowed_rejects_everyone_else_once_the_whitelist_is_set() -> None:
    assert inline_allowed(8, (7, 9)) is False


def test_inline_allowed_rejects_an_unknown_user_when_gated() -> None:
    assert inline_allowed(None, (7,)) is False


def test_inline_allowed_lets_an_unknown_user_through_when_open() -> None:
    assert inline_allowed(None, ()) is True


def test_build_results_puts_the_deadline_first() -> None:
    """The first result is what pressing enter sends: it must be the information,
    never the invite."""
    deadline, invite = build_results("scadenza", "fantabot")
    assert deadline.id == RESULT_DEADLINE
    assert invite.id == RESULT_INVITE


def test_build_results_carries_the_texts_it_was_given() -> None:
    deadline, invite = build_results("scadenza", "fantabot")
    assert deadline.input_message_content.message_text == "scadenza"
    assert "https://t.me/fantabot" in invite.input_message_content.message_text


@pytest.mark.parametrize("result", build_results("scadenza", "fantabot"))
def test_build_results_are_html(result: object) -> None:
    assert result.input_message_content.parse_mode == "HTML"


def test_inline_invite_links_the_given_username() -> None:
    assert "https://t.me/fantabot" in messages.inline_invite("fantabot")
