import asyncio
from datetime import UTC, datetime, timedelta

from fantaformazionibot.calendar.mock import MockProvider


def test_fetch_matchdays_returns_round_one_near_future_kickoff() -> None:
    provider = MockProvider(timedelta(minutes=10))
    before = datetime.now(UTC)

    matchdays = asyncio.run(provider.fetch_matchdays())

    after = datetime.now(UTC)
    assert len(matchdays) == 1
    assert matchdays[0].round == 1
    kickoff = matchdays[0].kickoff
    # Truncated to the whole minute, so it can sit up to 59s before the lower bound.
    assert (kickoff.second, kickoff.microsecond) == (0, 0)
    assert before + timedelta(minutes=9) <= kickoff <= after + timedelta(minutes=10)


def test_fetch_matchdays_is_fresh_on_every_call() -> None:
    provider = MockProvider(timedelta(minutes=10))

    first = asyncio.run(provider.fetch_matchdays())
    second = asyncio.run(provider.fetch_matchdays())

    assert second[0].kickoff >= first[0].kickoff
