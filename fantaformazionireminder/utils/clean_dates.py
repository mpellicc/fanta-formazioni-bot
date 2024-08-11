import csv
from datetime import datetime, timedelta
from typing import List

import requests

import config


def __download_csv(url, dest_path) -> None:
    response = requests.get(url)
    with open(dest_path, "wb") as file:
        file.write(response.content)


def get_cleaned_dates() -> List[datetime]:
    # Download the CSV file
    __download_csv(config.SERIE_A_CALENDAR_URL.format(current_year = datetime.now().year), config.SERIE_A_CALENDAR_PATH)

    # Read the data from the CSV file
    with open(config.SERIE_A_CALENDAR_PATH, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        # Initialize a dictionary to store the earliest date for each round
        dates = {}

        # Iterate through each row in the CSV file
        for row in reader:
            # Extract date and time from the CSV row
            date_str = row["Date"]

            # Convert date string to datetime object
            date_obj = datetime.strptime(date_str, "%d/%m/%Y %H:%M")

            # Subtract 5 minutes from the datetime
            date_obj -= timedelta(minutes=5)

            # Extract round number from the CSV row
            round_number = int(row["Round Number"])

            # Update the earliest date for the round if needed
            if round_number not in dates or date_obj < dates[round_number]:
                dates[round_number] = date_obj

        # Convert the dictionary values to a sorted list
        results = sorted(dates.values())

    return results


if __name__ == "__main__":
    # Print the results as datetime objects
    cleaned_dates = get_cleaned_dates()
    for result in cleaned_dates:
        print(result)
