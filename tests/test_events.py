"""The dual-sink event emission of ADR 0029: one call, a log line and a row."""

import logging
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

from fantaformazionibot.storage.repository import Repository
from fantaformazionibot.telegram import commands
from fantaformazionibot.telegram.events import log_event, record_process_event


def _rows(tmp_path: Path) -> list[tuple[str, str, int | None, str | None, str | None]]:
    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        return list(
            conn.execute(
                "SELECT action, outcome, chat_id, chat_type, detail FROM bot_events ORDER BY id"
            )
        )
    finally:
        conn.close()


def test_log_event_without_a_repository_only_logs(
    tmp_path: Path, caplog: "logging.LogCaptureFixture"
) -> None:
    repository = Repository(tmp_path / "test.db")

    with caplog.at_level(logging.INFO):
        log_event("subscribe", 42, "created", chat_type="private")

    assert "action=subscribe chat_id=42 outcome=created chat_type=private" in caplog.text
    assert _rows(tmp_path) == []
    repository.close()


def test_log_event_with_a_repository_logs_and_records(
    tmp_path: Path, caplog: "logging.LogCaptureFixture"
) -> None:
    repository = Repository(tmp_path / "test.db")

    with caplog.at_level(logging.INFO):
        log_event("subscribe", 42, "created", repository=repository, chat_type="private")

    assert "action=subscribe chat_id=42 outcome=created chat_type=private" in caplog.text
    assert _rows(tmp_path) == [("subscribe", "created", 42, "private", None)]


def test_none_valued_fields_reach_neither_sink(tmp_path: Path) -> None:
    repository = Repository(tmp_path / "test.db")

    log_event("subscribe", 42, "created", repository=repository, chat_type=None, thread_id=None)

    assert _rows(tmp_path) == [("subscribe", "created", 42, None, None)]


def test_a_failing_record_does_not_break_the_caller(
    tmp_path: Path, caplog: "logging.LogCaptureFixture"
) -> None:
    """Metrics are secondary to the function they measure (ADR 0029)."""
    repository = MagicMock()
    repository.record_event.side_effect = sqlite3.OperationalError("database is locked")

    with caplog.at_level(logging.INFO):
        log_event("reminder_send", 42, "sent", repository=repository)

    assert "action=reminder_send chat_id=42 outcome=sent" in caplog.text
    assert "Failed to record event reminder_send" in caplog.text


def test_process_events_have_no_chat_and_no_log_line(
    tmp_path: Path, caplog: "logging.LogCaptureFixture"
) -> None:
    repository = Repository(tmp_path / "test.db")

    with caplog.at_level(logging.INFO):
        record_process_event(repository, "calendar_refresh", "ok", matchdays=380)

    assert "action=calendar_refresh" not in caplog.text
    assert _rows(tmp_path) == [("calendar_refresh", "ok", None, None, '{"matchdays": 380}')]


def test_confirming_a_lineup_records_the_event(tmp_path: Path) -> None:
    """The core functions of commands.py are the single covered path for both the
    command and its callback (ADR 0028 §3), so the row lands whichever is used."""
    repository = Repository(tmp_path / "test.db")

    commands.confirm_lineup(42, 7, repository, MagicMock())
    commands.undo_lineup_confirmation(42, 7, repository, MagicMock())

    assert [(action, outcome) for action, outcome, *_ in _rows(tmp_path)] == [
        ("lineup_confirm", "confirmed"),
        ("lineup_undo", "undone"),
    ]


def test_a_repeated_confirmation_is_recorded_as_a_noop(tmp_path: Path) -> None:
    """ADR 0024's distinction survives into the DB: counting real confirmations stays
    a matter of counting one outcome."""
    repository = Repository(tmp_path / "test.db")

    commands.confirm_lineup(42, 7, repository, MagicMock())
    commands.confirm_lineup(42, 7, repository, MagicMock())

    assert [outcome for _, outcome, *_ in _rows(tmp_path)] == ["confirmed", "noop"]
