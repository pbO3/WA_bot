import dateparser
from datetime import datetime
import pytz
from datetime import timedelta
import re

IST = pytz.timezone("Asia/Kolkata")

def normalize_human_time(text: str):
    text = text.lower()

    replacements = {
        r"\bmorning\b": "9:00 am",
        r"\bsubah\b": "9:00 am",
        r"\bafternoon\b": "3:00 pm",
        r"\bdopahar\b": "3:00 pm",
        r"\bevening\b": "6:00 pm",
        r"\bshaam\b": "6:00 pm",
        r"\bnight\b": "9:00 pm",
        r"\braat\b": "9:00 pm",
    }

    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)

    return text






def parse_time(time_text):

    if not time_text:
        return None

    time_text = normalize_human_time(time_text)
        print(time_text)    
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
