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
