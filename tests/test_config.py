from datetime import timedelta

import pytest

from fantaformazionibot.config import Settings, parse_duration


def test_parse_duration() -> None:
    assert parse_duration("30s") == timedelta(seconds=30)
    assert parse_duration("5m") == timedelta(minutes=5)
    assert parse_duration("24h") == timedelta(hours=24)
    assert parse_duration("2g") == timedelta(days=2)


@pytest.mark.parametrize("value", ["", "5", "5d", "abc", "1h30m"])
def test_parse_duration_rejects_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        parse_duration(value)


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "token": "test-token",
        "channel_chat_id": -100,
        "debug_chat_id": 1,
    }
    return Settings(_env_file=None, **{**defaults, **overrides})  # type: ignore[call-arg]


def test_settings_parses_compact_durations_from_env_strings() -> None:
    settings = _settings(deadline_margin="10m", reminder_offsets="24h,90m,30s")

    assert settings.deadline_margin == timedelta(minutes=10)
    assert settings.reminder_offsets == (
        timedelta(hours=24),
        timedelta(minutes=90),
        timedelta(seconds=30),
    )


def test_settings_parses_allowed_chat_ids() -> None:
    assert _settings().allowed_chat_ids == ()
    assert _settings(allowed_chat_ids="").allowed_chat_ids == ()
    assert _settings(allowed_chat_ids="42, -1002171697436").allowed_chat_ids == (
        42,
        -1002171697436,
    )


def test_settings_defaults() -> None:
    settings = _settings()

    assert settings.deadline_margin == timedelta(minutes=5)
    assert settings.reminder_offsets == (
        timedelta(hours=24),
        timedelta(hours=1),
        timedelta(minutes=5),
    )
    assert settings.calendar_provider == "fixturedownload"
    assert "{season_year}" in settings.calendar_url
