"""Pure reminder-planning logic: no I/O, trivially testable. See ADR 0005/0006."""

from collections.abc import Sequence
from datetime import datetime, timedelta

from fantaformazionibot.models import Matchday, PlannedReminder, Subscription


def deadline_for(matchday: Matchday, margin: timedelta) -> datetime:
    """The lineup deadline: the round's first kickoff minus the safety margin."""
    return matchday.kickoff - margin


def next_deadline(
    matchdays: Sequence[Matchday], margin: timedelta, now: datetime
) -> tuple[Matchday, datetime] | None:
    """The first matchday whose deadline is still in the future, with its deadline."""
    upcoming = [(m, deadline_for(m, margin)) for m in matchdays if deadline_for(m, margin) > now]
    if not upcoming:
        return None
    return min(upcoming, key=lambda pair: pair[1])


def is_placeholder_kickoff(kickoff: datetime) -> bool:
    """fixturedownload marks not-yet-confirmed kickoffs with an all-zero UTC time."""
    return (kickoff.hour, kickoff.minute, kickoff.second) == (0, 0, 0)


def stale_matchday(
    matchdays: Sequence[Matchday], margin: timedelta, now: datetime, threshold: timedelta
) -> Matchday | None:
    """The next matchday, if its deadline is imminent but its kickoff still looks unset.

    See ADR 0014: fixturedownload exposes no reliable "last updated" signal, so
    this is a content-based heuristic on the one placeholder pattern observed.
    """
    upcoming = next_deadline(matchdays, margin, now)
    if upcoming is None:
        return None
    matchday, deadline = upcoming
    if deadline - now <= threshold and is_placeholder_kickoff(matchday.kickoff):
        return matchday
    return None


def plan_reminders(
    matchdays: Sequence[Matchday],
    subscriptions: Sequence[Subscription],
    margin: timedelta,
    now: datetime,
) -> list[PlannedReminder]:
    """Every future reminder (deadline - offset) for every subscription, soonest first."""
    planned = [
        PlannedReminder(
            chat_id=subscription.chat_id,
            round=matchday.round,
            offset_seconds=offset_seconds,
            when=deadline_for(matchday, margin) - timedelta(seconds=offset_seconds),
        )
        for matchday in matchdays
        for subscription in subscriptions
        for offset_seconds in subscription.reminder_offsets
    ]
    return sorted((r for r in planned if r.when > now), key=lambda r: r.when)
