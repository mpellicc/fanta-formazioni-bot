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
    """Remaining time, e.g. '1 giorno e 3 ore'.

    Past 7 days, a coarser top unit (week, or month past 30 days — a flat 30-day
    approximation, display-only) is shown first, followed by up to two of the
    existing day/hour/minute units for the remainder, e.g. '1 mese, 12 giorni e 23
    ore' or '2 settimane e 14 ore'. Below 7 days, behaviour is unchanged: the two
    largest non-zero day/hour/minute units.
    """
    seconds = max(int((deadline - now).total_seconds()), 0)
    total_days = seconds // 86400
    parts: list[str] = []
    cap = 2
    if total_days >= 30:
        months, seconds = divmod(seconds, 2592000)
        parts.append(f"{months} {'mese' if months == 1 else 'mesi'}")
        cap = 3
    elif total_days >= 7:
        weeks, seconds = divmod(seconds, 604800)
        parts.append(f"{weeks} {'settimana' if weeks == 1 else 'settimane'}")
        cap = 3
    for unit_seconds, singular, plural in _UNITS:
        amount, seconds = divmod(seconds, unit_seconds)
        if amount > 0:
            parts.append(f"{amount} {singular if amount == 1 else plural}")
        if len(parts) == cap:
            break
    if not parts:
        return "meno di 1 minuto"
    return join_list(parts)


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
