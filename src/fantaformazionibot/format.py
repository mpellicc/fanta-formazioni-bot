"""Italian date/duration formatting. No system locale involved; display timezone only here."""

from collections.abc import Sequence
from datetime import datetime, timedelta

from fantaformazionibot.config import TIMEZONE

_MONTHS = (
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)

_UNITS = (
    (86400, "giorno", "giorni"),
    (3600, "ora", "ore"),
    (60, "minuto", "minuti"),
)


def format_date(dt: datetime) -> str:
    """E.g. '15 marzo'."""
    local = dt.astimezone(TIMEZONE)
    return f"{local.day} {_MONTHS[local.month - 1]}"


def format_time(dt: datetime) -> str:
    """E.g. '18:25' (Europe/Rome)."""
    return dt.astimezone(TIMEZONE).strftime("%H:%M")


def format_remaining(deadline: datetime, now: datetime) -> str:
    """Remaining time in the two largest non-zero units, e.g. '1 giorno e 3 ore'."""
    seconds = max(int((deadline - now).total_seconds()), 0)
    parts: list[str] = []
    for unit_seconds, singular, plural in _UNITS:
        amount, seconds = divmod(seconds, unit_seconds)
        if amount > 0:
            parts.append(f"{amount} {singular if amount == 1 else plural}")
        if len(parts) == 2:
            break
    if not parts:
        return "meno di 1 minuto"
    return " e ".join(parts)


def format_duration(duration: timedelta) -> str:
    """A duration in its largest exact unit, e.g. 24h → '1 giorno', 1h → '1 ora'."""
    seconds = int(duration.total_seconds())
    for unit_seconds, singular, plural in _UNITS:
        if seconds >= unit_seconds and seconds % unit_seconds == 0:
            amount = seconds // unit_seconds
            return f"{amount} {singular if amount == 1 else plural}"
    return f"{seconds} {'secondo' if seconds == 1 else 'secondi'}"


def join_list(items: Sequence[str]) -> str:
    """Italian-style enumeration: 'a, b e c'."""
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} e {items[-1]}"
