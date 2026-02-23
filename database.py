import sqlite3
from time_utils import now_ist, IST
from datetime import timedelta
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")


conn = sqlite3.connect("tasks.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT,
    due_time TEXT,
    status TEXT DEFAULT 'pending'
)
""")

def add_task(task, due_datetime):
    due_time_str = due_datetime.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO tasks (task, due_time, status)
        VALUES (?, ?, 'pending')
    """, (task, due_time_str))
    conn.commit()

def get_active_tasks(limit=15):
    
    cursor.execute("""
        SELECT id, task, due_time, status
        FROM tasks
        WHERE status != 'done'
        ORDER BY due_time ASC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()

    return rows



def get_all_tasks():
    cursor.execute("SELECT * FROM tasks")
    return cursor.fetchall()

def get_due_tasks():
    cursor = conn.cursor()
    now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        SELECT id, task
        FROM tasks
        WHERE due_time <= ?
        AND status = 'pending'
    """, (now_str,))

    return cursor.fetchall()

def mark_asked(task_id):
    cursor.execute("UPDATE tasks SET status='asked' WHERE id=?", (task_id,))
    conn.commit()


def delete_old_tasks():
    cutoff = now_ist() - timedelta(days=1)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M")
    cursor.execute("DELETE FROM tasks WHERE due_time < ?", (cutoff_str,))
    conn.commit()

def mark_asked(task_id):
    cursor.execute("UPDATE tasks SET status='asked' WHERE id=?", (task_id,))
    conn.commit()


def get_last_asked():
    cursor.execute("SELECT id FROM tasks WHERE status='asked' ORDER BY id DESC LIMIT 1")
    result = cursor.fetchone()
    return result[0] if result else None

def mark_done(task_id):
    cursor.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
    conn.commit()


def snooze_task(task_id, minutes):
    from datetime import datetime, timedelta

    cursor.execute("SELECT due_time FROM tasks WHERE id=?", (task_id,))
    due = cursor.fetchone()[0]

    # Parse stored IST time
    due_dt = IST.localize(datetime.strptime(due, "%Y-%m-%d %H:%M:%S"))

    # Add snooze
    new_time = due_dt + timedelta(minutes=minutes)
    
    cursor.execute("UPDATE tasks SET due_time=?, status='pending' WHERE id=?",
                   (new_time.strftime("%Y-%m-%d %H:%M:%S"), task_id))
    conn.commit()

