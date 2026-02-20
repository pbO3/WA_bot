from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

def now_ist():
    return datetime.now(IST)

def to_ist(dt):
    if dt.tzinfo is None:
        return IST.localize(dt)
    return dt.astimezone(IST)


def human_time(due_time_str):
    dt = datetime.strptime(due_time_str, "%Y-%m-%d %H:%M:%S")
    dt = IST.localize(dt)

    now = datetime.now(IST)
    today = now.date()

    # overdue
    if dt < now:
        return "⚠️ overdue"

    # today
    if dt.date() == today:
        return f"Today {dt.strftime('%I:%M %p')}"

    # tomorrow
    if (dt.date() - today).days == 1:
        return f"Tomorrow {dt.strftime('%I:%M %p')}"

    # future
    return dt.strftime("%d %b %I:%M %p")