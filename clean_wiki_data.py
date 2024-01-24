import csv
import os
from datetime import datetime, timedelta
from typing import Final, List

import requests
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Constants
CSV_PATH: Final = os.getenv("SERIE_A_CALENDAR_PATH")
CSV_URL: Final = os.getenv("SERIE_A_CALENDAR_URL")

def download_csv(url, dest_path) -> None:
    response = requests.get(url)
    with open(dest_path, 'wb') as file:
        file.write(response.content)

def get_cleaned_dates() -> List[datetime]:
    
    # Download the CSV file
    download_csv(CSV_URL, CSV_PATH)
    
    # Read the data from the CSV file
    with open(CSV_PATH, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        # Initialize a dictionary to store the earliest date for each round
        dates = {}

        # Map month names to integers using a dictionary
        months_mapping = {
            "gen.": 1, "feb.": 2, "mar.": 3, "apr.": 4, "mag.": 5, "giu.": 6,
            "lug.": 7, "ago.": 8, "set.": 9, "ott.": 10, "nov.": 11, "dic.": 12,
        }

        # Iterate through each row in the CSV file
        for row in reader:
            # Extract date and time from the CSV row
            date_str = row["Date"]
            time_str = date_str.split()[-1]  # Extract time from the end of the date string

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
