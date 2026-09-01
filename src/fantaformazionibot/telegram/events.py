"""One-line, greppable events for the log stream (ADR 0028).

Every user-visible state change goes through log_event, which renders a fixed
`action=... chat_id=... outcome=...` prefix plus optional extra fields. The
dashboard filters on those `key=` tokens, so values must stay single tokens
(no spaces): pass ids and short slugs, never free prose or user text.
"""

import logging

logger = logging.getLogger("fantaformazionibot.events")


def log_event(action: str, chat_id: int, outcome: str, **fields: object) -> None:
    """Log one event. Fields whose value is None are omitted, so callers can pass
    optional context (round, user_id, thread_id) unconditionally."""
    parts = [f"action={action}", f"chat_id={chat_id}", f"outcome={outcome}"]
    parts.extend(f"{key}={value}" for key, value in fields.items() if value is not None)
    logger.info(" ".join(parts))
