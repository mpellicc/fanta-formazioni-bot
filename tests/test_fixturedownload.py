from datetime import UTC, datetime
from pathlib import Path

from fantaformazionibot.calendar.fixturedownload import parse_matchdays

FIXTURE = Path(__file__).parent / "fixtures" / "calendar.csv"


def test_parse_matchdays_earliest_kickoff_per_round() -> None:
    matchdays = parse_matchdays(FIXTURE.read_text(encoding="utf-8"))

    assert [m.round for m in matchdays] == [1, 2]
    assert matchdays[0].kickoff == datetime(2025, 8, 17, 16, 30, tzinfo=UTC)
    # round 2's earliest fixture is the 23rd, not the row listed first
    assert matchdays[1].kickoff == datetime(2025, 8, 23, 18, 45, tzinfo=UTC)


def test_parse_matchdays_skips_non_numeric_rounds() -> None:
    matchdays = parse_matchdays(FIXTURE.read_text(encoding="utf-8"))
    assert all(isinstance(m.round, int) for m in matchdays)


def test_parse_matchdays_kickoffs_are_utc_aware() -> None:
    matchdays = parse_matchdays(FIXTURE.read_text(encoding="utf-8"))
    assert all(m.kickoff.tzinfo == UTC for m in matchdays)
