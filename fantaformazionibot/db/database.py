import sqlite3
from pathlib import Path
from typing import List

from db.model.match import Match


def create_tables(database_file: Path) -> None:
    conn = sqlite3.connect(database_file)
    cur = conn.cursor()

    # Create matches table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY,
            match_date_time DATETIME NOT NULL
        )
    """)

    # Create notifications table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            match_id INTEGER NOT NULL,
            notification_time INTEGER NOT NULL,
            UNIQUE (match_id, notification_time),
            FOREIGN KEY (match_id) REFERENCES matches (id)
        )
    """)

    conn.commit()
    conn.close()


def save_matches(database_file: Path, matches: List[Match]) -> None:
    conn = sqlite3.connect(database_file)
    cur = conn.cursor()

    for match in matches:
        cur.execute('''
            INSERT OR REPLACE INTO matches (id, match_date_time) VALUES (?, ?)
        ''', (match.id, match.formatted_datetime()))

    conn.commit()
    conn.close()


def _upsert_match(cur: sqlite3.Cursor, match: Match) -> None:
    # Check if the match already exists
    cur.execute(
        """
        SELECT id FROM matches WHERE id = ?
    """,
        (match.id,),
    )

    existing_match = cur.fetchone()

    if existing_match:
        # Update the existing match
        cur.execute(
            """
            UPDATE matches
            SET match_datetime = ?
            WHERE id = ?
        """,
            (match.formatted_datetime(), match.id),
        )
    else:
        # Insert the new match
        cur.execute(
            """
            INSERT INTO matches (id, match_datetime) VALUES (?, ?)
        """,
            (match.id, match.formatted_datetime()),
        )


def record_notification_sent(
    database_file: Path, match_id: int, notification_time: int
) -> None:
    conn = sqlite3.connect(database_file)
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO notifications (match_id, notification_time)
            VALUES (?, ?)
        """,
            (match_id, notification_time),
        )
    except sqlite3.IntegrityError:
        # Handle the case where the notification already exists, if needed
        pass

    conn.commit()
    conn.close()
