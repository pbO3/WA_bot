import dateparser
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

def parse_time(time_text):

    if not time_text:
        return None

    parsed = dateparser.parse(
        time_text,
        settings={
            "TIMEZONE": "Asia/Kolkata",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future"
        },
        languages=["en", "hi"]
    )

    if parsed is None:
        return None

    # normalize timezone
    parsed = parsed.astimezone(IST)

    return parsed   # <-- return datetime, NOT string
