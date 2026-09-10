from datetime import UTC, datetime

import pytest
from telegram import (
    Chat,
    ChatMemberAdministrator,
    ChatMemberBanned,
    ChatMemberLeft,
    ChatMemberMember,
    ChatMemberUpdated,
    User,
)

from fantaformazionibot.telegram.chatmember import is_bot_added

_BOT = User(id=42, is_bot=True, first_name="Fanta Formazioni")


def _member(status: str) -> object:
    if status == "left":
        return ChatMemberLeft(user=_BOT)
    if status == "kicked":
        return ChatMemberBanned(user=_BOT, until_date=None)
    if status == "administrator":
        return ChatMemberAdministrator(
            user=_BOT,
            can_be_edited=False,
            is_anonymous=False,
            can_manage_chat=True,
            can_delete_messages=False,
            can_manage_video_chats=False,
            can_restrict_members=False,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=False,
            can_post_stories=False,
            can_edit_stories=False,
            can_delete_stories=False,
        )
    return ChatMemberMember(user=_BOT)


def _update(old: str, new: str) -> ChatMemberUpdated:
    return ChatMemberUpdated(
        chat=Chat(id=-100, type="supergroup"),
        from_user=User(id=1, is_bot=False, first_name="Mister"),
        date=datetime.now(UTC),
        old_chat_member=_member(old),  # type: ignore[arg-type]
        new_chat_member=_member(new),  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("old", "new"),
    [("left", "member"), ("left", "administrator"), ("kicked", "member")],
)
def test_is_bot_added_on_a_real_entrance(old: str, new: str) -> None:
    assert is_bot_added(_update(old, new)) is True


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("member", "administrator"),  # promoted while already in the chat
        ("administrator", "member"),  # demoted
        ("member", "member"),  # permissions edited
        ("member", "left"),  # removed
        ("administrator", "kicked"),
    ],
)
def test_is_bot_added_ignores_everything_that_is_not_an_entrance(old: str, new: str) -> None:
    """my_chat_member fires on promotions and permission edits too: those must not
    re-send the welcome to a group that already has it (ADR 0032)."""
    assert is_bot_added(_update(old, new)) is False
