import sqlite3
import uuid
from datetime import datetime, timedelta
import pytz
from time_utils import now_ist, IST

IST = pytz.timezone("Asia/Kolkata")

# ── Single source of truth for DB path ──
DB_PATH = "tasks.db"

# ── Single shared connection for original task functions ──
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# ──────────────────────────────────────────────
#  ORIGINAL TABLES (unchanged)
# ──────────────────────────────────────────────

cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT,
    due_time TEXT,
    status TEXT DEFAULT 'pending'
)
""")

# ──────────────────────────────────────────────
#  NEW TABLES — called once here at startup
# ──────────────────────────────────────────────

def init_conversation_table():
    c = sqlite3.connect(DB_PATH).cursor()
    c.connection.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_number TEXT NOT NULL,
            role            TEXT NOT NULL,
            content         TEXT NOT NULL,
            timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.connection.commit()
    c.connection.close()

def init_pending_table():
    c = sqlite3.connect(DB_PATH).cursor()
    c.connection.execute("""
        CREATE TABLE IF NOT EXISTS pending_questions (
            id              TEXT PRIMARY KEY,
            customer_number TEXT NOT NULL,
            question        TEXT NOT NULL,
            status          TEXT DEFAULT 'pending',
            reminder_sent   INTEGER DEFAULT 0,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at     DATETIME
        )
    """)
    c.connection.commit()
    c.connection.close()

# ── Call both immediately at import time ──
init_conversation_table()
init_pending_table()


# ──────────────────────────────────────────────
#  ORIGINAL TASK FUNCTIONS (completely unchanged)
# ──────────────────────────────────────────────

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
    return cursor.fetchall()

def get_all_tasks():
    cursor.execute("SELECT * FROM tasks")
    return cursor.fetchall()

def get_due_tasks():
    cur = conn.cursor()
    now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        SELECT id, task
        FROM tasks
        WHERE due_time <= ?
        AND status = 'pending'
    """, (now_str,))
    return cur.fetchall()

def mark_asked(task_id):
    cursor.execute("UPDATE tasks SET status='asked' WHERE id=?", (task_id,))
    conn.commit()

def delete_old_tasks():
    cutoff = now_ist() - timedelta(days=1)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M")
    cursor.execute("DELETE FROM tasks WHERE due_time < ?", (cutoff_str,))
    conn.commit()

def get_last_asked():
    cursor.execute("SELECT id FROM tasks WHERE status='asked' ORDER BY id DESC LIMIT 1")
    result = cursor.fetchone()
    return result[0] if result else None

def mark_done(task_id):
    cursor.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
    conn.commit()

def snooze_task(task_id, minutes):
    cursor.execute("SELECT due_time FROM tasks WHERE id=?", (task_id,))
    due = cursor.fetchone()[0]
    due_dt = IST.localize(datetime.strptime(due, "%Y-%m-%d %H:%M:%S"))
    new_time = due_dt + timedelta(minutes=minutes)
    cursor.execute(
        "UPDATE tasks SET due_time=?, status='pending' WHERE id=?",
        (new_time.strftime("%Y-%m-%d %H:%M:%S"), task_id)
    )
    conn.commit()


# ──────────────────────────────────────────────
#  NEW FUNCTIONS — conversation memory + fallback
# ──────────────────────────────────────────────

def save_conversation_turn(customer_number: str, role: str, content: str):
    c = sqlite3.connect(DB_PATH)
    c.execute(
        "INSERT INTO conversations (customer_number, role, content) VALUES (?, ?, ?)",
        (customer_number, role, content)
    )
    c.commit()
    c.close()

def get_conversation_history(customer_number: str, limit: int = 20) -> list:
    c = sqlite3.connect(DB_PATH)
    cur = c.execute(
        """SELECT role, content FROM conversations
           WHERE customer_number = ?
           ORDER BY timestamp DESC LIMIT ?""",
        (customer_number, limit)
    )
    rows = cur.fetchall()
    c.close()
    rows.reverse()
    return [{"role": row[0], "content": row[1]} for row in rows]