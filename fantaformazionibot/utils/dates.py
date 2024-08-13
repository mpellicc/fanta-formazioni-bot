import csv
from datetime import datetime, timedelta
from typing import Dict, List

from config import Config
from db.model.match import Match
from utils.csv import download_csv
from utils.logging import get_logger

# Get logger
logger = get_logger()


def get_clean_dates(config: Config) -> List[Match]:
    # Download the CSV file
    logger.debug(
        f"Downloading matches calendar file from {config.serie_a_calendar_url}"
    )
    download_csv(config.serie_a_calendar_url, config.serie_a_calendar_path)

    # Read the data from the CSV file
    logger.debug("Reading matches file...")
    with open(config.serie_a_calendar_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        # Initialize a dictionary to store the earliest date for each round
        matches: Dict[Match] = {}

        # Iterate through each row in the CSV file
        for row in reader:
            # Extract date and time from the CSV row
            date_str = row["Date"]

            # Convert date string to datetime object
            datetime_obj = datetime.strptime(date_str, "%d/%m/%Y %H:%M")

            # Subtract 5 minutes from the datetime
            datetime_obj -= timedelta(minutes=5)

            # Extract round number from the CSV row
            round_number = int(row["Round Number"])

            # Update the earliest date for the round if needed
            if (
                round_number not in matches
                or datetime_obj < matches[round_number].match_datetime
            ):
                matches[round_number] = Match(
                    id=round_number, match_datetime=datetime_obj
                )

        # Convert the dictionary values to a sorted list
        return sorted(matches.values(), key=lambda match: match.id)
