import datetime
import os
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

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
    def serie_a_calendar_path(self) -> Path:
        path = self.RESOURCES_DIR / os.getenv("SERIE_A_CALENDAR_PATH", "calendar.csv")
        return path.resolve()

    @property
    def serie_a_calendar_url(self) -> str:
        return os.getenv(
            "SERIE_A_CALENDAR_URL",
            "https://fixturedownload.com/download/serie-a-{current_year}-WEuropeStandardTime.csv",
        ).format(current_year=datetime.now().year)
