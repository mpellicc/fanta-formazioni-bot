import os
from datetime import datetime
from pathlib import Path
from typing import Final

from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# Load .env
load_dotenv()


class Config:
    BASE_DIR: Final[Path] = Path(__file__).resolve().parent
    RESOURCES_DIR: Final[Path] = BASE_DIR / "resources"

    @property
    def token(self) -> str:
        token = os.getenv("TOKEN")
        if token is None:
            raise ValueError("TOKEN environment variable not set.")
        return token

    @property
    def bot_username(self) -> str:
        bot_username = os.getenv("BOT_USERNAME")
        if bot_username is None:
            raise ValueError("BOT_USERNAME environment variable not set.")
        return bot_username

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo("Europe/Rome")

    @property
    def serie_a_calendar_path(self) -> Path:
        path = self.RESOURCES_DIR / os.getenv("SERIE_A_CALENDAR_PATH", "calendar.csv")
        return path.resolve()

    @property
    def serie_a_calendar_url(self) -> str:
        return os.getenv(
            "SERIE_A_CALENDAR_URL",
            "https://fixturedownload.com/download/serie-a-{season_year}-WEuropeStandardTime.csv",
        ).format(season_year=self._get_season_year())

    @property
    def database_file(self) -> Path:
        path = self.RESOURCES_DIR / os.getenv("DATABASE_PATH", "fantaformazionibot.db")
        return path.resolve()

    @property
    def channel_chat_id(self) -> str:
        channel_chat_id = os.getenv("CHANNEL_CHAT_ID")
        if channel_chat_id is None:
            raise ValueError("CHANNEL_CHAT_ID environment variable not set.")
        return channel_chat_id

    @property
    def developer_chat_id(self) -> str:
        developer_chat_id = os.getenv("DEVELOPER_CHAT_ID")
        if developer_chat_id is None:
            raise ValueError("DEVELOPER_CHAT_ID environment variable not set.")
        return developer_chat_id

    @staticmethod
    def _get_season_year() -> int:
        return (
            datetime.now().year
            if datetime.now().month >= 7
            else (datetime.now().year - 1)
        )
