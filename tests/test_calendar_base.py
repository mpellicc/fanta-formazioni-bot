from datetime import UTC, datetime

import pytest

from fantaformazionibot.calendar.base import create_provider, season_year
from fantaformazionibot.calendar.fixturedownload import FixtureDownloadProvider
from fantaformazionibot.calendar.football_data_org import FootballDataOrgProvider
from fantaformazionibot.calendar.mock import MockProvider
from fantaformazionibot.config import CalendarProvider, Settings


def test_season_year_rolls_over_in_july() -> None:
    assert season_year(datetime(2026, 7, 6, tzinfo=UTC)) == 2026
    assert season_year(datetime(2026, 6, 30, tzinfo=UTC)) == 2025
    assert season_year(datetime(2026, 1, 15, tzinfo=UTC)) == 2025


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "token": "test-token",
        "channel_chat_id": -100,
        "debug_chat_id": 1,
    }
    return Settings(_env_file=None, **{**defaults, **overrides})  # type: ignore[call-arg]


def test_create_provider_fixturedownload() -> None:
    provider = create_provider(_settings())
    assert isinstance(provider, FixtureDownloadProvider)


def test_create_provider_football_data_org() -> None:
    provider = create_provider(
        _settings(
            calendar_provider=CalendarProvider.FOOTBALL_DATA_ORG,
            football_data_api_key="secret",
        )
    )
    assert isinstance(provider, FootballDataOrgProvider)


def test_create_provider_football_data_org_requires_api_key() -> None:
    with pytest.raises(ValueError, match="FOOTBALL_DATA_API_KEY"):
        create_provider(_settings(calendar_provider=CalendarProvider.FOOTBALL_DATA_ORG))


def test_create_provider_mock() -> None:
    provider = create_provider(_settings(calendar_provider=CalendarProvider.MOCK))
    assert isinstance(provider, MockProvider)
