import os
from typing import Final

from dotenv import load_dotenv

load_dotenv()


BASE_RESOURCES_PATH: Final = os.path.join(os.getcwd(), "fantaformazionireminder\\resources")

TOKEN: Final[str] = os.getenv("TOKEN")
BOT_USERNAME: Final[str] = os.getenv("BOT_USERNAME")

SAVED_DATES_FILEPATH: Final[str] = os.path.join(BASE_RESOURCES_PATH, os.getenv("SAVED_DATES_FILEPATH"))
CHAT_IDS_FILEPATH: Final[str] = os.path.join(BASE_RESOURCES_PATH, os.getenv("CHAT_IDS_FILEPATH"))

SERIE_A_CALENDAR_PATH: Final = os.path.join(BASE_RESOURCES_PATH, os.getenv("SERIE_A_CALENDAR_PATH"))
SERIE_A_CALENDAR_URL: Final = os.getenv("SERIE_A_CALENDAR_URL")