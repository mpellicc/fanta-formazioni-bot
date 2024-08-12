
from datetime import datetime

def date_format() -> str:
    return datetime.now().strftime('%Y-%m-%d')

def time_format() -> str:
    return datetime.now().strftime('%H:%M:%S')