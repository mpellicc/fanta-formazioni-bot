import os
from typing import Final

from dotenv import load_dotenv

# Load .env
load_dotenv()


TOKEN: Final[str] = os.getenv("TOKEN")