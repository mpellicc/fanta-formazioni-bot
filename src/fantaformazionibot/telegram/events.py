"""One-line, greppable events for the log stream (ADR 0028), and the same events
as rows in `bot_events` (ADR 0029).

Every user-visible state change goes through log_event, which renders a fixed
`action=... chat_id=... outcome=...` prefix plus optional extra fields. The
dashboard filters on those `key=` tokens, so values must stay single tokens
(no spaces): pass ids and short slugs, never free prose or user text.

Passing `repository` also appends the event to `bot_events`, where the
dashboard can ask time-based questions the log stream cannot answer (it is
rotated). Keeping both sinks behind this one function is what stops them from
disagreeing about what happened.
"""

import logging

from fantaformazionibot.storage.repository import Repository

logger = logging.getLogger("fantaformazionibot.events")


def log_event(
    action: str,
    chat_id: int,
    outcome: str,
    *,
    repository: Repository | None = None,
    **fields: object,
) -> None:
    """Log one event, and record it when a repository is given. Fields whose value is
    None are omitted, so callers can pass optional context (round, user_id, thread_id)
    unconditionally."""
    parts = [f"action={action}", f"chat_id={chat_id}", f"outcome={outcome}"]
    present = {key: value for key, value in fields.items() if value is not None}
    parts.extend(f"{key}={value}" for key, value in present.items())
    logger.info(" ".join(parts))
    if repository is not None:
        _record(repository, action, chat_id, outcome, present)


def record_process_event(
    repository: Repository, action: str, outcome: str, **fields: object
) -> None:
    """Record an event that belongs to no chat (startup, calendar refresh).

    DB only: the log line's `chat_id=` prefix is a contract towards the dashboard
    (ADR 0028 §5), and these events have no chat to put there. They keep the plain
    `logger` calls they already had at their call sites.
    """
    _record(
        repository,
        action,
        None,
        outcome,
        {key: value for key, value in fields.items() if value is not None},
    )


def _record(
    repository: Repository,
    action: str,
    chat_id: int | None,
    outcome: str,
    fields: dict[str, object],
) -> None:
    """Metrics must never break the thing they measure: a failed insert is logged
    and swallowed, so a reminder still goes out and a command still answers."""
    try:
        repository.record_event(action, chat_id, outcome, fields)
    except Exception:
        logger.exception("Failed to record event %s", action)
