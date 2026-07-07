from datetime import UTC, datetime

from fantaformazionibot.calendar.football_data_org import parse_matches

MATCHES = [
    {"matchday": 1, "utcDate": "2025-08-17T16:30:00Z", "status": "SCHEDULED"},
    {"matchday": 1, "utcDate": "2025-08-17T18:45:00Z", "status": "SCHEDULED"},
    {"matchday": 2, "utcDate": "2025-08-23T18:45:00Z", "status": "SCHEDULED"},
]


def test_parse_matches_earliest_kickoff_per_round() -> None:
    matchdays = parse_matches(MATCHES)

    assert [m.round for m in matchdays] == [1, 2]
    assert matchdays[0].kickoff == datetime(2025, 8, 17, 16, 30, tzinfo=UTC)
    assert matchdays[1].kickoff == datetime(2025, 8, 23, 18, 45, tzinfo=UTC)


def test_parse_matches_kickoffs_are_utc_aware() -> None:
    matchdays = parse_matches(MATCHES)
    assert all(m.kickoff.tzinfo == UTC for m in matchdays)
