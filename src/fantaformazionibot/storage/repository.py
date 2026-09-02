import json
import sqlite3
from collections.abc import Mapping, Sequence
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
                    origin TEXT NOT NULL DEFAULT 'env',
                    created_at TEXT,
                    message_thread_id INTEGER
                )
                """
            )
            # Pre-origin databases: existing rows are the env-seeded channel.
            columns = {row[1] for row in self._conn.execute("PRAGMA table_info(subscriptions)")}
            if "origin" not in columns:
                self._conn.execute(
                    "ALTER TABLE subscriptions ADD COLUMN origin TEXT NOT NULL DEFAULT 'env'"
                )
            # Pre-created_at databases: existing rows predate tracking, so leave them NULL
            # rather than backfilling a fabricated join date (ADR 0022).
            if "created_at" not in columns:
                self._conn.execute("ALTER TABLE subscriptions ADD COLUMN created_at TEXT")
            # Pre-forum-topic databases: existing rows have no bound topic (ADR 0025).
            if "message_thread_id" not in columns:
                self._conn.execute("ALTER TABLE subscriptions ADD COLUMN message_thread_id INTEGER")
            # Append-only lifecycle log: subscriptions only ever holds the active
            # set, so leaving is otherwise invisible (ADR 0024).
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS subscription_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    chat_type TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    event TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS subscription_events_chat_idx
                ON subscription_events (chat_id, occurred_at)
                """
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
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lineup_confirmations (
                    chat_id INTEGER NOT NULL,
                    round INTEGER NOT NULL,
                    UNIQUE (chat_id, round)
                )
                """
            )
            # Group roster (ADR 0027): the Bot API cannot enumerate non-admin members, so
            # the roster is built lazily from self-registrations and confirmations.
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS group_participants (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    joined_at TEXT NOT NULL,
                    UNIQUE (chat_id, user_id)
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS group_rosters (
                    chat_id INTEGER PRIMARY KEY,
                    closed_at TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS group_lineup_confirmations (
                    chat_id INTEGER NOT NULL,
                    round INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    UNIQUE (chat_id, round, user_id)
                )
                """
            )
            # Append-only log of what happened and when (ADR 0029). The state tables
            # above are point-in-time and some of them get cleared (reopen_roster),
            # so every time-based metric has to come from here instead.
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    chat_id INTEGER,
                    chat_type TEXT,
                    user_id INTEGER,
                    round INTEGER,
                    detail TEXT
                )
                """
            )
            for name, columns_sql in (
                ("bot_events_time_idx", "(occurred_at)"),
                ("bot_events_action_idx", "(action, occurred_at)"),
                ("bot_events_chat_idx", "(chat_id, occurred_at)"),
            ):
                self._conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON bot_events {columns_sql}")

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
        # _post_init re-seeds the env channel on every restart and /promemoria_on
        # is idempotent, so only a row that wasn't there is a new subscriber.
        is_new = self.get_subscription(subscription.chat_id) is None
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO subscriptions
                    (chat_id, chat_type, reminder_offsets, origin, created_at, message_thread_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (chat_id) DO UPDATE SET
                    chat_type = excluded.chat_type,
                    reminder_offsets = excluded.reminder_offsets,
                    origin = excluded.origin
                    -- message_thread_id is deliberately NOT updated here, same as
                    -- created_at above: _post_init re-seeds the env channel on every
                    -- restart, and a bound topic must survive that reseed untouched
                    -- (moving it goes through update_subscription_thread instead).
                """,
                (
                    subscription.chat_id,
                    subscription.chat_type,
                    json.dumps(list(subscription.reminder_offsets)),
                    subscription.origin,
                    datetime.now(UTC).isoformat(),
                    subscription.message_thread_id,
                ),
            )
            if is_new:
                self._record_event(
                    subscription.chat_id, subscription.chat_type, subscription.origin, "subscribed"
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
            "SELECT chat_id, chat_type, reminder_offsets, origin, message_thread_id"
            " FROM subscriptions WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        if row is None:
            return None
        chat_id, chat_type, offsets, origin, message_thread_id = row
        return Subscription(
            chat_id=chat_id,
            chat_type=chat_type,
            reminder_offsets=tuple(json.loads(offsets)),
            origin=origin,
            message_thread_id=message_thread_id,
        )

    def update_subscription_offsets(self, chat_id: int, offsets_seconds: Sequence[int]) -> bool:
        """Update reminder_offsets on an existing subscription; report whether a row matched."""
        with self._conn:
            cursor = self._conn.execute(
                "UPDATE subscriptions SET reminder_offsets = ? WHERE chat_id = ?",
                (json.dumps(list(offsets_seconds)), chat_id),
            )
        return cursor.rowcount > 0

    def update_subscription_thread(self, chat_id: int, message_thread_id: int | None) -> bool:
        """Update message_thread_id on an existing subscription; report whether a row matched."""
        with self._conn:
            cursor = self._conn.execute(
                "UPDATE subscriptions SET message_thread_id = ? WHERE chat_id = ?",
                (message_thread_id, chat_id),
            )
        return cursor.rowcount > 0

    def delete_user_subscription(self, chat_id: int) -> bool:
        """/promemoria_off: the chat is still a known user, it just stopped
        wanting reminders. Reported as whether a row was deleted."""
        return self._delete_user_subscription(chat_id, "unsubscribed")

    def prune_dead_subscription(self, chat_id: int) -> bool:
        """The chat can no longer receive anything — blocked, kicked, gone (ADR 0023).
        Same deletion, logged as a different kind of leaving (ADR 0024)."""
        return self._delete_user_subscription(chat_id, "dead_chat")

    def _delete_user_subscription(self, chat_id: int, event: str) -> bool:
        """Delete the chat's subscription if user-owned; report whether a row was deleted.

        The env-seeded channel row is owned by config (ADR 0012): commands
        must not delete it, hence the origin filter.
        """
        leaving = self.get_subscription(chat_id)
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM subscriptions WHERE chat_id = ? AND origin = 'user'",
                (chat_id,),
            )
            if cursor.rowcount > 0 and leaving is not None:
                self._record_event(chat_id, leaving.chat_type, leaving.origin, event)
        return cursor.rowcount > 0

    def _record_event(self, chat_id: int, chat_type: str, origin: str, event: str) -> None:
        """Append one lifecycle event. Call inside an open transaction: the row must
        land with the subscriptions change it describes, or not at all."""
        self._conn.execute(
            """
            INSERT INTO subscription_events (chat_id, chat_type, origin, event, occurred_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, chat_type, origin, event, datetime.now(UTC).isoformat()),
        )

    def get_subscriptions(self) -> list[Subscription]:
        rows = self._conn.execute(
            "SELECT chat_id, chat_type, reminder_offsets, origin, message_thread_id"
            " FROM subscriptions"
        )
        return [
            Subscription(
                chat_id=chat_id,
                chat_type=chat_type,
                reminder_offsets=tuple(json.loads(offsets)),
                origin=origin,
                message_thread_id=message_thread_id,
            )
            for chat_id, chat_type, offsets, origin, message_thread_id in rows
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

    # --- lineup confirmations ---

    def is_lineup_confirmed(self, chat_id: int, round_: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM lineup_confirmations WHERE chat_id = ? AND round = ?",
            (chat_id, round_),
        ).fetchone()
        return row is not None

    def mark_lineup_confirmed(self, chat_id: int, round_: int) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO lineup_confirmations (chat_id, round) VALUES (?, ?)",
                (chat_id, round_),
            )

    def unmark_lineup_confirmed(self, chat_id: int, round_: int) -> bool:
        """Delete the confirmation if present; report whether one was deleted."""
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM lineup_confirmations WHERE chat_id = ? AND round = ?",
                (chat_id, round_),
            )
        return cursor.rowcount > 0

    def clear_lineup_confirmations(self, chat_id: int) -> None:
        """Drop every silencing flag for a chat. Used when a group roster is reset (ADR 0027)."""
        with self._conn:
            self._conn.execute("DELETE FROM lineup_confirmations WHERE chat_id = ?", (chat_id,))

    # --- group roster (ADR 0027) ---

    def add_group_participant(self, chat_id: int, user_id: int) -> bool:
        """Add a manager to the chat roster; report whether they were new."""
        with self._conn:
            cursor = self._conn.execute(
                """
                INSERT OR IGNORE INTO group_participants (chat_id, user_id, joined_at)
                VALUES (?, ?, ?)
                """,
                (chat_id, user_id, datetime.now(UTC).isoformat()),
            )
        return cursor.rowcount > 0

    def get_group_participants(self, chat_id: int) -> list[int]:
        rows = self._conn.execute(
            "SELECT user_id FROM group_participants WHERE chat_id = ? ORDER BY joined_at",
            (chat_id,),
        ).fetchall()
        return [user_id for (user_id,) in rows]

    def count_group_participants(self, chat_id: int) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM group_participants WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        return int(row[0])

    def is_roster_closed(self, chat_id: int) -> bool:
        row = self._conn.execute(
            "SELECT closed_at FROM group_rosters WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        return row is not None and row[0] is not None

    def close_roster(self, chat_id: int) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO group_rosters (chat_id, closed_at) VALUES (?, ?)
                ON CONFLICT (chat_id) DO UPDATE SET closed_at = excluded.closed_at
                """,
                (chat_id, datetime.now(UTC).isoformat()),
            )

    def reopen_roster(self, chat_id: int) -> None:
        """Reopen enrollment, dropping the roster and its confirmations (ADR 0027).

        A reset roster must not carry confirmations of managers who are no longer there.
        """
        with self._conn:
            self._conn.execute("DELETE FROM group_participants WHERE chat_id = ?", (chat_id,))
            self._conn.execute(
                "DELETE FROM group_lineup_confirmations WHERE chat_id = ?", (chat_id,)
            )
            self._conn.execute(
                """
                INSERT INTO group_rosters (chat_id, closed_at) VALUES (?, NULL)
                ON CONFLICT (chat_id) DO UPDATE SET closed_at = NULL
                """,
                (chat_id,),
            )

    # --- group lineup confirmations (ADR 0027) ---

    def is_group_lineup_confirmed(self, chat_id: int, round_: int, user_id: int) -> bool:
        row = self._conn.execute(
            """
            SELECT 1 FROM group_lineup_confirmations
            WHERE chat_id = ? AND round = ? AND user_id = ?
            """,
            (chat_id, round_, user_id),
        ).fetchone()
        return row is not None

    def mark_group_lineup_confirmed(self, chat_id: int, round_: int, user_id: int) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO group_lineup_confirmations (chat_id, round, user_id)
                VALUES (?, ?, ?)
                """,
                (chat_id, round_, user_id),
            )

    def unmark_group_lineup_confirmed(self, chat_id: int, round_: int, user_id: int) -> bool:
        """Delete one manager's confirmation if present; report whether one was deleted."""
        with self._conn:
            cursor = self._conn.execute(
                """
                DELETE FROM group_lineup_confirmations
                WHERE chat_id = ? AND round = ? AND user_id = ?
                """,
                (chat_id, round_, user_id),
            )
        return cursor.rowcount > 0

    def count_group_lineup_confirmations(self, chat_id: int, round_: int) -> int:
        """Count confirmations from managers who are actually on the roster."""
        row = self._conn.execute(
            """
            SELECT COUNT(*) FROM group_lineup_confirmations AS c
            WHERE c.chat_id = ? AND c.round = ? AND EXISTS (
                SELECT 1 FROM group_participants AS p
                WHERE p.chat_id = c.chat_id AND p.user_id = c.user_id
            )
            """,
            (chat_id, round_),
        ).fetchone()
        return int(row[0])

    def is_group_lineup_complete(self, chat_id: int, round_: int) -> bool:
        """Whether every known participant has confirmed. Empty roster is never complete."""
        total = self.count_group_participants(chat_id)
        if total == 0:
            return False
        return self.count_group_lineup_confirmations(chat_id, round_) >= total

    # --- events (ADR 0029) ---

    # Promoted to columns because they are the axes the dashboard aggregates on;
    # everything else rides along in `detail` as JSON.
    _EVENT_COLUMNS = ("chat_type", "user_id", "round")

    def record_event(
        self,
        action: str,
        chat_id: int | None,
        outcome: str,
        fields: Mapping[str, object] | None = None,
    ) -> None:
        """Append one fact, with its instant and its outcome. Never an intention."""
        extra = dict(fields or {})
        promoted = {name: extra.pop(name, None) for name in self._EVENT_COLUMNS}
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO bot_events
                    (occurred_at, action, outcome, chat_id, chat_type, user_id, round, detail)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(UTC).isoformat(),
                    action,
                    outcome,
                    chat_id,
                    promoted["chat_type"],
                    promoted["user_id"],
                    promoted["round"],
                    json.dumps(extra, default=str) if extra else None,
                ),
            )
