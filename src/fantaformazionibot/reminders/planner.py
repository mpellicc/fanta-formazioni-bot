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
