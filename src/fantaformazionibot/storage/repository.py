import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from fantaformazionibot.models import Matchday, Subscription


class Repository:
    """Single owner of the SQLite database and all SQL. See ADR 0004."""

    def __init__(self, database_path: Path) -> None:
        self._conn = sqlite3.connect(database_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def close(self) -> None:
        self._conn.close()

    def _create_tables(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS matchdays (
                    round INTEGER PRIMARY KEY,
                    kickoff_utc TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS subscriptions (
                    chat_id INTEGER PRIMARY KEY,
                    chat_type TEXT NOT NULL,
                    reminder_offsets TEXT NOT NULL,
                    origin TEXT NOT NULL DEFAULT 'env'
                )
                """
            )
            # Pre-origin databases: existing rows are the env-seeded channel.
            columns = {row[1] for row in self._conn.execute("PRAGMA table_info(subscriptions)")}
            if "origin" not in columns:
                self._conn.execute(
                    "ALTER TABLE subscriptions ADD COLUMN origin TEXT NOT NULL DEFAULT 'env'"
                )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sent_reminders (
                    chat_id INTEGER NOT NULL,
                    round INTEGER NOT NULL,
                    offset_seconds INTEGER NOT NULL,
                    UNIQUE (chat_id, round, offset_seconds)
                )
                """
            )

    # --- matchdays ---

    def upsert_matchdays(self, matchdays: Sequence[Matchday]) -> None:
        with self._conn:
            self._conn.executemany(
                """
                INSERT INTO matchdays (round, kickoff_utc) VALUES (?, ?)
                ON CONFLICT (round) DO UPDATE SET kickoff_utc = excluded.kickoff_utc
                """,
                [(m.round, m.kickoff.astimezone(UTC).isoformat()) for m in matchdays],
            )

    def get_matchdays(self) -> list[Matchday]:
        rows = self._conn.execute("SELECT round, kickoff_utc FROM matchdays ORDER BY round")
        return [self._to_matchday(round_, kickoff) for round_, kickoff in rows]

    def get_matchday(self, round_: int) -> Matchday | None:
        row = self._conn.execute(
            "SELECT round, kickoff_utc FROM matchdays WHERE round = ?", (round_,)
        ).fetchone()
        return self._to_matchday(*row) if row else None

    @staticmethod
    def _to_matchday(round_: int, kickoff_utc: str) -> Matchday:
        return Matchday(round=round_, kickoff=datetime.fromisoformat(kickoff_utc))

    # --- subscriptions ---

    def upsert_subscription(self, subscription: Subscription) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO subscriptions (chat_id, chat_type, reminder_offsets, origin)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (chat_id) DO UPDATE SET
                    chat_type = excluded.chat_type,
                    reminder_offsets = excluded.reminder_offsets,
                    origin = excluded.origin
                """,
                (
                    subscription.chat_id,
                    subscription.chat_type,
                    json.dumps(list(subscription.reminder_offsets)),
                    subscription.origin,
                ),
            )

    def prune_channel_subscriptions(self, keep_chat_id: int) -> None:
        """Drop env-owned channel subscriptions other than the configured one.

        When CHANNEL_CHAT_ID changes, the previously seeded row must not keep
        receiving reminders. Only rows with origin='env' are considered:
        user-created subscriptions (any type, channels included) are untouched.
        """
        with self._conn:
            self._conn.execute(
                """
                DELETE FROM subscriptions
                WHERE origin = 'env' AND chat_type = 'channel' AND chat_id != ?
                """,
                (keep_chat_id,),
            )

    def get_subscription(self, chat_id: int) -> Subscription | None:
        row = self._conn.execute(
            "SELECT chat_id, chat_type, reminder_offsets, origin FROM subscriptions"
            " WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        if row is None:
            return None
        chat_id, chat_type, offsets, origin = row
        return Subscription(
            chat_id=chat_id,
            chat_type=chat_type,
            reminder_offsets=tuple(json.loads(offsets)),
            origin=origin,
        )

    def update_subscription_offsets(self, chat_id: int, offsets_seconds: Sequence[int]) -> bool:
        """Update reminder_offsets on an existing subscription; report whether a row matched."""
        with self._conn:
            cursor = self._conn.execute(
                "UPDATE subscriptions SET reminder_offsets = ? WHERE chat_id = ?",
                (json.dumps(list(offsets_seconds)), chat_id),
            )
        return cursor.rowcount > 0

    def delete_user_subscription(self, chat_id: int) -> bool:
        """Delete the chat's subscription if user-owned; report whether a row was deleted.

        The env-seeded channel row is owned by config (ADR 0012): commands
        must not delete it, hence the origin filter.
        """
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM subscriptions WHERE chat_id = ? AND origin = 'user'",
                (chat_id,),
            )
        return cursor.rowcount > 0

    def get_subscriptions(self) -> list[Subscription]:
        rows = self._conn.execute(
            "SELECT chat_id, chat_type, reminder_offsets, origin FROM subscriptions"
        )
        return [
            Subscription(
                chat_id=chat_id,
                chat_type=chat_type,
                reminder_offsets=tuple(json.loads(offsets)),
                origin=origin,
            )
            for chat_id, chat_type, offsets, origin in rows
        ]

    # --- sent reminders ---

    def was_reminder_sent(self, chat_id: int, round_: int, offset_seconds: int) -> bool:
        row = self._conn.execute(
            """
            SELECT 1 FROM sent_reminders
            WHERE chat_id = ? AND round = ? AND offset_seconds = ?
            """,
            (chat_id, round_, offset_seconds),
        ).fetchone()
        return row is not None

    def mark_reminder_sent(self, chat_id: int, round_: int, offset_seconds: int) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO sent_reminders (chat_id, round, offset_seconds)
                VALUES (?, ?, ?)
                """,
                (chat_id, round_, offset_seconds),
            )
