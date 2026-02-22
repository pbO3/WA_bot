import dateparser
from datetime import datetime
import pytz
from datetime import timedelta

IST = pytz.timezone("Asia/Kolkata")

def parse_time(time_text):

    if not time_text:
        return None

    parsed = dateparser.parse(
        time_text,
        settings={
            "TIMEZONE": "Asia/Kolkata",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": datetime.now(IST)
        },
        languages=["en", "hi"]
    )

    if parsed is None:
        return None

    # normalize timezone
    parsed = parsed.astimezone(IST)

    now = datetime.now(IST)

    if parsed < now:
        parsed = parsed + timedelta(days=1)

    return parsed   # <-- return datetime, NOT string
