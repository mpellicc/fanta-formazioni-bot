from datetime import UTC, datetime, timedelta

from fantaformazionibot.models import Matchday, Subscription
from fantaformazionibot.reminders import planner

MARGIN = timedelta(minutes=5)

ROUND_1 = Matchday(round=1, kickoff=datetime(2025, 8, 17, 16, 30, tzinfo=UTC))
ROUND_2 = Matchday(round=2, kickoff=datetime(2025, 8, 23, 18, 45, tzinfo=UTC))

CHANNEL = Subscription(chat_id=-100, chat_type="channel", reminder_offsets=(86400, 3600, 300))


def test_deadline_is_kickoff_minus_margin() -> None:
    assert planner.deadline_for(ROUND_1, MARGIN) == datetime(2025, 8, 17, 16, 25, tzinfo=UTC)


def test_next_deadline_picks_first_future_deadline() -> None:
    now = datetime(2025, 8, 17, 16, 26, tzinfo=UTC)  # round 1 deadline just passed
    upcoming = planner.next_deadline([ROUND_1, ROUND_2], MARGIN, now)

    assert upcoming is not None
    matchday, deadline = upcoming
    assert matchday.round == 2
    assert deadline == datetime(2025, 8, 23, 18, 40, tzinfo=UTC)


def test_next_deadline_none_when_season_over() -> None:
    now = datetime(2026, 6, 1, tzinfo=UTC)
    assert planner.next_deadline([ROUND_1, ROUND_2], MARGIN, now) is None


def test_plan_reminders_only_future_sorted() -> None:
    now = datetime(2025, 8, 17, 12, 0, tzinfo=UTC)  # between round 1's 24h and 1h reminders
    plan = planner.plan_reminders([ROUND_1, ROUND_2], [CHANNEL], MARGIN, now)

    assert [(r.round, r.offset_seconds) for r in plan] == [
        (1, 3600),
        (1, 300),
        (2, 86400),
        (2, 3600),
        (2, 300),
    ]
    assert all(r.when > now for r in plan)
    assert plan[0].when == datetime(2025, 8, 17, 15, 25, tzinfo=UTC)


def test_plan_reminders_multiple_subscriptions() -> None:
    other = Subscription(chat_id=42, chat_type="private", reminder_offsets=(600,))
    now = datetime(2025, 8, 1, tzinfo=UTC)
    plan = planner.plan_reminders([ROUND_1], [CHANNEL, other], MARGIN, now)

    assert {(r.chat_id, r.offset_seconds) for r in plan} == {
        (-100, 86400),
        (-100, 3600),
        (-100, 300),
        (42, 600),
    }
