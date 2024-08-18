import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from db.model.match import Match
from utils.logging import get_logger

logger = get_logger(__name__)


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

    logger.info("Saving matches to database")
    for match in matches:
        cur.execute(
            """
            INSERT OR REPLACE INTO matches (id, match_date_time) VALUES (?, ?)
        """,
            (match.id, match.formatted_datetime()),
        )

    conn.commit()
    conn.close()


def get_next_match(database_file: Path, current_time: datetime) -> Match:
    conn = sqlite3.connect(database_file)
    cur = conn.cursor()

    # Get the current datetime
    current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")

    # Execute the query to get the next match
    cur.execute(
        """
        SELECT id, match_date_time
        FROM matches
        WHERE match_date_time > ?
        ORDER BY match_date_time ASC
        LIMIT 1;
    """,
        (current_time_str,),
    )

    next_match: Tuple[int, str] = cur.fetchone()
    conn.close()

    if next_match:
        match_id, match_date_time = next_match
        logger.debug(f"Next match: {match_id} ({match_date_time})")

        return Match.from_datetime_str(match_id, match_date_time)
    else:
        logger.debug("No upcoming matches found")
        return None


def get_notifications_by_match_id(database_file: Path, match_id: int) -> List[int]:
    """
    Retrieve notifications for a specific match by match_id.

    :param database_file: The path to the SQLite database file.
    :param match_id: The ID of the match for which to retrieve notifications.
    :return: A list of tuples, each containing (notification_time, match_id).
    """
    conn = sqlite3.connect(database_file)
    cur = conn.cursor()

    # Query to get notifications for the specific match_id
    cur.execute(
        """
        SELECT notification_time
        FROM notifications
        WHERE match_id = ?
    """,
        (match_id,),
    )

    # Fetch all notification times
    # notifications = cur.fetchall()
    notification_times = [row[0] for row in cur.fetchall()]
    print("Stop")

    conn.close()

    return notification_times


def record_notification_sent(
    database_file: Path, match_id: int, notification_time: int
) -> None:
    conn = sqlite3.connect(database_file)
    cur = conn.cursor()

    logger.info(
        f"Saving notification with time: [{notification_time}] for match with id: [{match_id}]"
    )
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
