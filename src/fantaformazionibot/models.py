from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Matchday:
    """A Serie A matchday, identified by its round and the kickoff of its first fixture."""

    round: int
    kickoff: datetime  # tz-aware, UTC


@dataclass(frozen=True, slots=True)
class Subscription:
    """A chat that receives lineup reminders."""

    chat_id: int
    chat_type: str
    reminder_offsets: tuple[int, ...]  # seconds before the deadline


@dataclass(frozen=True, slots=True)
class PlannedReminder:
    """A single reminder to be delivered to a chat at an exact time."""

    chat_id: int
    round: int
    offset_seconds: int
    when: datetime  # tz-aware, UTC
