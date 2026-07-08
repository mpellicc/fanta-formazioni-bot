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
        return [Matchday(round=_MOCK_ROUND, kickoff=datetime.now(UTC) + self._kickoff_offset)]
