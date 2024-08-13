from dataclasses import dataclass
from datetime import datetime


@dataclass
class Match:
    id: int
    match_datetime: datetime

    def formatted_datetime(self) -> str:
        """Return the match datetime as a formatted string."""
        return self.match_datetime.strftime("%Y-%m-%d %H:%M:%S")
