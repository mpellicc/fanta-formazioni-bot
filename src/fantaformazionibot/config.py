import re
from datetime import time, timedelta
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

TIMEZONE = ZoneInfo("Europe/Rome")

_DURATION_RE = re.compile(r"^\s*(\d+)\s*([smh])\s*$")
_DURATION_UNITS = {"s": 1, "m": 60, "h": 3600}


def parse_duration(value: str) -> timedelta:
    """Parse a compact duration string such as '5m', '24h' or '30s'."""
    matched = _DURATION_RE.match(value)
    if matched is None:
        raise ValueError(f"invalid duration {value!r}, expected e.g. '5m', '24h', '30s'")
    return timedelta(seconds=int(matched.group(1)) * _DURATION_UNITS[matched.group(2)])


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    token: str
    channel_chat_id: int
    debug_chat_id: int

    calendar_provider: str = "fixturedownload"
    calendar_url: str = "https://fixturedownload.com/download/serie-a-{season_year}-UTC.csv"
    calendar_refresh_time: time = time(hour=2, minute=0)  # Europe/Rome
    database_path: Path = Path("fantaformazionibot.db")
    deadline_margin: timedelta = timedelta(minutes=5)
    reminder_offsets: Annotated[tuple[timedelta, ...], NoDecode] = (
        timedelta(hours=24),
        timedelta(hours=1),
        timedelta(minutes=5),
    )

    @field_validator("deadline_margin", mode="before")
    @classmethod
    def _parse_margin(cls, value: object) -> object:
        if isinstance(value, str):
            return parse_duration(value)
        return value

    @field_validator("reminder_offsets", mode="before")
    @classmethod
    def _parse_offsets(cls, value: object) -> object:
        if isinstance(value, str):
            offsets = tuple(parse_duration(part) for part in value.split(","))
            if not offsets:
                raise ValueError("REMINDER_OFFSETS must contain at least one duration")
            return offsets
        return value
