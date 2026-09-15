from datetime import UTC, datetime, timedelta

from fantaformazionibot.models import Matchday

_MOCK_ROUND = 1


class MockProvider:
    """Fabricates a near-future kickoff for round 1 (ADR 0016, dev-only testing aid).

    Reuses round 1 rather than a synthetic round number: upsert_matchdays only
    INSERTs/UPDATEs, never deletes, so a made-up round would linger forever
    after switching back to a real provider. Round 1 is the row the real
    providers already populate for the season opener, so the next real
    refresh simply overwrites the kickoff back to the true value.
    """

    def __init__(self, kickoff_offset: timedelta) -> None:
        self._kickoff_offset = kickoff_offset

    async def fetch_matchdays(self) -> list[Matchday]:
        # Whole minute, like every real provider: fixturedownload parses "%d/%m/%Y %H:%M"
        # and football-data.org returns ...T16:30:00Z, so deadlines and reminders always
        # land on a round minute. A kickoff carrying seconds would make dev runs drift
        # from production timing by up to a minute, which is not what a test aid is for.
        kickoff = (datetime.now(UTC) + self._kickoff_offset).replace(second=0, microsecond=0)
        return [Matchday(round=_MOCK_ROUND, kickoff=kickoff)]
