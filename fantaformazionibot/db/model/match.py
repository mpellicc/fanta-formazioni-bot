from dataclasses import dataclass
from datetime import datetime

from dateutil import parser, tz

from config import Config

config: Config = Config()


@dataclass
class Match:
    id: int
    match_datetime: datetime

    @classmethod
    def from_datetime_str(cls, id: int, match_datetime_str: str) -> "Match":
        # Convert the string to a datetime object
        match_datetime = parser.parse(match_datetime_str)
        match_datetime = match_datetime.replace(tzinfo=tz.tzutc())
        match_datetime = match_datetime.astimezone(tz.gettz(config.timezone))

        # Return an instance of the Match dataclass
        return cls(id=id, match_datetime=match_datetime)

    def formatted_datetime(self) -> str:
        """Return the match datetime as a formatted string."""
        return self.match_datetime.strftime("%Y-%m-%d %H:%M:%S")
