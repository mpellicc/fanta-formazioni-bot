import sqlite3
from pathlib import Path


def create_tables(database_file: Path) -> None:
    conn = sqlite3.connect(database_file)
    cur = conn.cursor()

    # Create matches table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY,
            match_date DATE NOT NULL,
            match_time TIME NOT NULL
        )
    """)

    # Create notifications table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY,
            match_id INTEGER NOT NULL,
            notification_time INTEGER NOT NULL,
            sent BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (match_id) REFERENCES matches (id)
        )
    """)

    conn.commit()
    conn.close()
