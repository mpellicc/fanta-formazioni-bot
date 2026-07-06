from datetime import UTC, datetime, timedelta

from fantaformazionibot import format as fmt


def test_format_date_italian_month_local_timezone() -> None:
    # 23:30 UTC on Aug 16 is 01:30 CEST on Aug 17
    dt = datetime(2025, 8, 16, 23, 30, tzinfo=UTC)
    assert fmt.format_date(dt) == "17 agosto"


def test_format_time_converts_to_rome() -> None:
    assert fmt.format_time(datetime(2025, 8, 17, 16, 30, tzinfo=UTC)) == "18:30"  # CEST
    assert fmt.format_time(datetime(2026, 1, 10, 19, 45, tzinfo=UTC)) == "20:45"  # CET


def test_format_remaining_two_largest_units() -> None:
    now = datetime(2025, 8, 17, 12, 0, tzinfo=UTC)
    assert fmt.format_remaining(now + timedelta(days=1, hours=3, minutes=10), now) == (
        "1 giorno e 3 ore"
    )
    assert fmt.format_remaining(now + timedelta(hours=2, minutes=15), now) == "2 ore e 15 minuti"
    assert fmt.format_remaining(now + timedelta(minutes=5), now) == "5 minuti"
    assert fmt.format_remaining(now + timedelta(seconds=30), now) == "meno di 1 minuto"
    assert fmt.format_remaining(now - timedelta(minutes=1), now) == "meno di 1 minuto"


def test_format_duration_largest_exact_unit() -> None:
    assert fmt.format_duration(timedelta(hours=24)) == "1 giorno"
    assert fmt.format_duration(timedelta(hours=1)) == "1 ora"
    assert fmt.format_duration(timedelta(minutes=5)) == "5 minuti"
    assert fmt.format_duration(timedelta(minutes=90)) == "90 minuti"
    assert fmt.format_duration(timedelta(seconds=30)) == "30 secondi"


def test_join_list() -> None:
    assert fmt.join_list(["1 giorno", "1 ora", "5 minuti"]) == "1 giorno, 1 ora e 5 minuti"
    assert fmt.join_list(["1 ora"]) == "1 ora"
    assert fmt.join_list([]) == ""
