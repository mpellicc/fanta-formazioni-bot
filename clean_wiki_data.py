import re
from typing import Final
from datetime import datetime, timedelta


def get_cleaned_dates():
    # Specify the file path
    file_path: Final = "seriea_calendar.txt"

    # Read the data from the file with explicit encoding
    with open(file_path, "r", encoding="utf-8") as file:
        data = file.read()

    # Initialize a list to store the results as datetime objects
    results = []

    # Split the data into giornate using a regular expression
    giornate = re.split(r"(\d+ª giornata)", data)[1:]

    # Map month names to integers using a dictionary
    months_mapping = {
        "gen.": 1,
        "feb.": 2,
        "mar.": 3,
        "apr.": 4,
        "mag.": 5,
        "giu.": 6,
        "lug.": 7,
        "ago.": 8,
        "set.": 9,
        "ott.": 10,
        "nov.": 11,
        "dic.": 12,
    }

    # Iterate through each giornata (skip every second element since it's the giornata header)
    for i in range(0, len(giornate), 2):
        giornata_header = giornate[i]
        giornata_content = giornate[i + 1]

        # Extract the giornata number from the header using regex search
        giornata_number = re.search(r"(\d+)ª giornata", giornata_header)
        if giornata_number:
            current_giornata = giornata_number.group(1)

        # Extract the date and time from the giornata_content using regex findall
        date_matches = re.findall(r"(\d+ \w+\.)", giornata_content)
        if date_matches:
            # Split the date and month name and format them properly
            dates = [date_match.split() for date_match in date_matches]
            formatted_dates = [f"{date[0]} {months_mapping[date[1]]}" for date in dates]
            
            # Find the earliest date in the formatted dates list
            earliest_date_str = min(formatted_dates)

            # Get the year from the matched month
            matched_month = dates[formatted_dates.index(earliest_date_str)][1]
            year = 2024 if months_mapping[matched_month] <= 8 else 2023

            # Extract the time from giornata_content using regex search, or assume 18:00 if not found
            time_match = re.search(r"(\d+:\d+)", giornata_content)
            time = time_match.group(1) if time_match else "18:00"
            
            # Subtract 2 days from the date if time is not found
            if not time_match:
                earliest_date = datetime.strptime(earliest_date_str, "%d %m")
                earliest_date -= timedelta(days=2)
                earliest_date_str = earliest_date.strftime("%d %m")

            # Combine the date, year, and time into a single string
            earliest_datetime_str = f"{earliest_date_str} {year} {time}"

            # Convert the earliest_datetime_str to a datetime object
            earliest_datetime = datetime.strptime(earliest_datetime_str, "%d %m %Y %H:%M")

            # Subtract 5 minutes from the datetime
            earliest_datetime -= timedelta(minutes=5)

            # Add the datetime object to the results list
            results.append(earliest_datetime)

    return results


if __name__ == "__main__":
    # Print the results as datetime objects
    cleaned_dates = get_cleaned_dates()
    for result in cleaned_dates:
        print(result)
