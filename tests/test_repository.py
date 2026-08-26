import sqlite3
from datetime import datetime
from pathlib import Path

from fantaformazionibot.models import Subscription
from fantaformazionibot.storage.repository import Repository

ENV_CHANNEL = Subscription(
    chat_id=-100, chat_type="channel", reminder_offsets=(86400,), origin="env"
)
USER_CHANNEL = Subscription(
    chat_id=-200, chat_type="channel", reminder_offsets=(3600,), origin="user"
)
USER_PRIVATE = Subscription(chat_id=42, chat_type="private", reminder_offsets=(300,), origin="user")


def _repository(tmp_path: Path) -> Repository:
    return Repository(tmp_path / "test.db")


def _created_at(tmp_path: Path, chat_id: int) -> str | None:
    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        row = conn.execute(
            "SELECT created_at FROM subscriptions WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def test_upsert_and_get_subscriptions_roundtrip(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.upsert_subscription(ENV_CHANNEL)
    repository.upsert_subscription(USER_PRIVATE)

    assert set(repository.get_subscriptions()) == {ENV_CHANNEL, USER_PRIVATE}


def test_prune_removes_only_stale_env_channels(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.upsert_subscription(ENV_CHANNEL)
    repository.upsert_subscription(USER_CHANNEL)
    repository.upsert_subscription(USER_PRIVATE)

    new_env_channel = Subscription(
        chat_id=-999, chat_type="channel", reminder_offsets=(86400,), origin="env"
    )
    repository.upsert_subscription(new_env_channel)
    repository.prune_channel_subscriptions(keep_chat_id=new_env_channel.chat_id)

    # the stale env channel is gone; user subscriptions (channel included) survive
    assert set(repository.get_subscriptions()) == {new_env_channel, USER_CHANNEL, USER_PRIVATE}


def test_prune_keeps_current_env_channel(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.upsert_subscription(ENV_CHANNEL)
    repository.prune_channel_subscriptions(keep_chat_id=ENV_CHANNEL.chat_id)

    assert repository.get_subscriptions() == [ENV_CHANNEL]


def test_get_subscription_found_and_missing(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.upsert_subscription(USER_PRIVATE)

    assert repository.get_subscription(USER_PRIVATE.chat_id) == USER_PRIVATE
    assert repository.get_subscription(12345) is None


def test_delete_user_subscription_removes_user_row(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.upsert_subscription(USER_PRIVATE)

    assert repository.delete_user_subscription(USER_PRIVATE.chat_id) is True
    assert repository.get_subscription(USER_PRIVATE.chat_id) is None


def test_delete_user_subscription_leaves_env_row(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.upsert_subscription(ENV_CHANNEL)

    assert repository.delete_user_subscription(ENV_CHANNEL.chat_id) is False
    assert repository.get_subscription(ENV_CHANNEL.chat_id) == ENV_CHANNEL


def test_delete_user_subscription_missing_row(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    assert repository.delete_user_subscription(12345) is False


def test_update_subscription_offsets_updates_existing_row(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.upsert_subscription(USER_PRIVATE)

    assert repository.update_subscription_offsets(USER_PRIVATE.chat_id, (86400, 3600)) is True

    updated = repository.get_subscription(USER_PRIVATE.chat_id)
    assert updated is not None
    assert updated.reminder_offsets == (86400, 3600)
    assert updated.origin == USER_PRIVATE.origin
    assert updated.chat_type == USER_PRIVATE.chat_type


def test_update_subscription_offsets_missing_row(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    assert repository.update_subscription_offsets(12345, (3600,)) is False


def test_is_lineup_confirmed_false_when_absent(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    assert repository.is_lineup_confirmed(42, 7) is False


def test_mark_lineup_confirmed_roundtrip(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.mark_lineup_confirmed(42, 7)

    assert repository.is_lineup_confirmed(42, 7) is True
    # a different round or chat is unaffected
    assert repository.is_lineup_confirmed(42, 8) is False
    assert repository.is_lineup_confirmed(43, 7) is False


def test_mark_lineup_confirmed_is_idempotent(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.mark_lineup_confirmed(42, 7)
    repository.mark_lineup_confirmed(42, 7)

    assert repository.is_lineup_confirmed(42, 7) is True


def test_unmark_lineup_confirmed_removes_row(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.mark_lineup_confirmed(42, 7)

    assert repository.unmark_lineup_confirmed(42, 7) is True
    assert repository.is_lineup_confirmed(42, 7) is False


def test_unmark_lineup_confirmed_missing_row(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    assert repository.unmark_lineup_confirmed(42, 7) is False


def test_upsert_sets_created_at_tz_aware_for_new_subscription(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.upsert_subscription(USER_PRIVATE)

    created_at = _created_at(tmp_path, USER_PRIVATE.chat_id)
    assert created_at is not None
    assert datetime.fromisoformat(created_at).tzinfo is not None


def test_upsert_on_existing_row_does_not_change_created_at(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.upsert_subscription(USER_PRIVATE)
    original_created_at = _created_at(tmp_path, USER_PRIVATE.chat_id)

    updated = Subscription(
        chat_id=USER_PRIVATE.chat_id,
        chat_type=USER_PRIVATE.chat_type,
        reminder_offsets=(3600,),
        origin=USER_PRIVATE.origin,
    )
    repository.upsert_subscription(updated)

    assert _created_at(tmp_path, USER_PRIVATE.chat_id) == original_created_at


def test_migration_adds_created_at_column_as_null_for_existing_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE subscriptions (
            chat_id INTEGER PRIMARY KEY,
            chat_type TEXT NOT NULL,
            reminder_offsets TEXT NOT NULL,
            origin TEXT NOT NULL DEFAULT 'env'
        )
        """
    )
    conn.execute(
        "INSERT INTO subscriptions (chat_id, chat_type, reminder_offsets, origin)"
        " VALUES (-100, 'channel', '[86400]', 'env')"
    )
    conn.commit()
    conn.close()

    repository = Repository(db_path)

    columns = {row[1] for row in repository._conn.execute("PRAGMA table_info(subscriptions)")}
    assert "created_at" in columns
    assert _created_at(tmp_path, -100) is None
