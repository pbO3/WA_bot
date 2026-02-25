import dateparser
from datetime import datetime
import pytz
from datetime import timedelta
import re

IST = pytz.timezone("Asia/Kolkata")

def clean_time_phrase(text: str):
    text = text.lower().strip()

    # remove common Hindi postpositions that confuse parsers
    junk_words = [
        r"\bko\b",
        r"\bme\b",
        r"\bmai\b",
        r"\bpar\b",
        r"\btak\b",
        r"\bse\b",
        r"\bha(i|e)?\b",
        r"\bhh\b"
    ]

    for junk in junk_words:
        text = re.sub(junk, "", text)

    # 2️⃣ Hinglish → English date words
    hinglish_map = {
        r"\baaj\b": "today",
        r"\baj\b": "today",
        r"\bkal\b": "tomorrow",
        r"\bsubah\b": "morning",
        r"\bshaam\b": "evening",
        r"\bsham\b": "evening",
        r"\braat\b": "night",
        r"\brat\b": "night",
        r"\babhi\b": "now",
        r"\bthodi der baad\b": "in 15 minutes",
        r"\baad mein\b": "later",
        r"\baad me\b": "later",
    }

    for pattern, replacement in hinglish_map.items():
        text = re.sub(pattern, replacement, text)


    # collapse extra spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text

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
        
    #New step added
    time_text = clean_time_phrase(time_text)

    
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
