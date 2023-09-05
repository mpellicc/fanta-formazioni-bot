from typing import Final
import pickle
from dotenv import load_dotenv
import os

from clean_wiki_data import get_cleaned_dates

# Load .env
load_dotenv()

# Constants
SAVED_DATES_FILEPATH: Final = os.getenv("SAVED_DATES_FILEPATH")

# Load the existing saved_dates or initialize an empty list
try:
    with open(SAVED_DATES_FILEPATH, "rb") as file:
        saved_dates = pickle.load(file)
except FileNotFoundError:
    saved_dates = []

# Get the default dates from the external script
default_dates = get_cleaned_dates()

# Append default dates to the saved_dates list
saved_dates.extend([(0, date) for date in default_dates])

# Save the updated saved_dates list to the file
with open(SAVED_DATES_FILEPATH, "wb") as file:
    pickle.dump(saved_dates, file)

print("[DEAFULT_DATE][FILE_UPDATE] Default dates added to saved_dates.")
