from datetime import datetime
from typing import Protocol

from fantaformazionibot.config import CalendarProvider as CalendarProviderName
from fantaformazionibot.config import Settings
from fantaformazionibot.models import Matchday


def season_year(now: datetime) -> int:
    """Serie A seasons are labelled by their starting year; rollover on July 1st."""
    return now.year if now.month >= 7 else now.year - 1


class CalendarProvider(Protocol):
    """Source of the season's matchdays. See ADR 0007."""

    async def fetch_matchdays(self) -> list[Matchday]: ...


def create_provider(settings: Settings) -> CalendarProvider:
    from fantaformazionibot.calendar.fixturedownload import FixtureDownloadProvider
    from fantaformazionibot.calendar.football_data_org import FootballDataOrgProvider

    match settings.calendar_provider:
        case CalendarProviderName.FIXTUREDOWNLOAD:
            return FixtureDownloadProvider(settings.calendar_url)
        case CalendarProviderName.FOOTBALL_DATA_ORG:
            if not settings.football_data_api_key:
                raise ValueError(
                    "FOOTBALL_DATA_API_KEY is required when CALENDAR_PROVIDER=football-data-org"
                )
            return FootballDataOrgProvider(settings.football_data_api_key)
