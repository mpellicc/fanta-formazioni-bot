from typing import Protocol

from fantaformazionibot.config import Settings
from fantaformazionibot.models import Matchday


class CalendarProvider(Protocol):
    """Source of the season's matchdays. See ADR 0007."""

    async def fetch_matchdays(self) -> list[Matchday]: ...


def create_provider(settings: Settings) -> CalendarProvider:
    from fantaformazionibot.calendar.fixturedownload import FixtureDownloadProvider

    match settings.calendar_provider:
        case "fixturedownload":
            return FixtureDownloadProvider(settings.calendar_url)
        case unknown:
            raise ValueError(f"unknown CALENDAR_PROVIDER {unknown!r}")
