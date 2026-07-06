import csv
import io
from datetime import UTC, datetime

import httpx

from fantaformazionibot.models import Matchday

_DATE_FORMAT = "%d/%m/%Y %H:%M"


def season_year(now: datetime) -> int:
    """Serie A seasons are labelled by their starting year; rollover on July 1st."""
    return now.year if now.month >= 7 else now.year - 1


def parse_matchdays(csv_text: str) -> list[Matchday]:
    """Extract each round's earliest kickoff from a fixturedownload UTC CSV export."""
    kickoffs: dict[int, datetime] = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        try:
            round_number = int(row["Round Number"])
        except ValueError:
            continue  # non-league rows (playoffs etc.) have non-numeric rounds
        kickoff = datetime.strptime(row["Date"], _DATE_FORMAT).replace(tzinfo=UTC)
        if round_number not in kickoffs or kickoff < kickoffs[round_number]:
            kickoffs[round_number] = kickoff
    return [Matchday(round=r, kickoff=k) for r, k in sorted(kickoffs.items())]


class FixtureDownloadProvider:
    def __init__(self, url_template: str) -> None:
        self._url_template = url_template

    async def fetch_matchdays(self) -> list[Matchday]:
        url = self._url_template.format(season_year=season_year(datetime.now(UTC)))
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        return parse_matchdays(response.text)
