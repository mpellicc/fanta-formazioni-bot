from datetime import UTC, datetime
from typing import Any

import httpx

from fantaformazionibot.calendar.base import season_year
from fantaformazionibot.models import Matchday

_BASE_URL = "https://api.football-data.org/v4"
_SERIE_A_COMPETITION_CODE = "SA"


def parse_matches(matches: list[dict[str, Any]]) -> list[Matchday]:
    """Extract each round's earliest kickoff from a football-data.org matches payload."""
    kickoffs: dict[int, datetime] = {}
    for match in matches:
        round_number = int(match["matchday"])
        kickoff = datetime.fromisoformat(match["utcDate"])
        if round_number not in kickoffs or kickoff < kickoffs[round_number]:
            kickoffs[round_number] = kickoff
    return [Matchday(round=r, kickoff=k) for r, k in sorted(kickoffs.items())]


class FootballDataOrgProvider:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def fetch_matchdays(self) -> list[Matchday]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{_BASE_URL}/competitions/{_SERIE_A_COMPETITION_CODE}/matches",
                headers={"X-Auth-Token": self._api_key},
                params={"season": season_year(datetime.now(UTC))},
            )
            response.raise_for_status()
        payload: dict[str, Any] = response.json()
        return parse_matches(payload["matches"])
