from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

def now_ist():
    return datetime.now(IST)

def to_ist(dt):
    if dt.tzinfo is None:
        return IST.localize(dt)
    return dt.astimezone(IST)
