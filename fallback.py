import os
import uuid
import sqlite3
from datetime import datetime
import pytz
from messenger import send_message, send_message_with_context

DB_PATH = "tasks.db"
IST = pytz.timezone("Asia/Kolkata")
OWNER_NUMBER = os.getenv("OWNER_NUMBER", "919315544065")

# How long before we remind owner + update customer (in minutes)
FALLBACK_TIMEOUT_MINUTES = int(os.getenv("FALLBACK_TIMEOUT_MINUTES", "30"))


# ──────────────────────────────────────────────
#  DB SETUP
# ──────────────────────────────────────────────

def init_pending_table():
    """
    Creates the pending_questions table.
    Call this once at startup in database.py
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS pending_questions (
            id              TEXT PRIMARY KEY,       -- short unique ID e.g. "a1b2c3"
            customer_number TEXT NOT NULL,          -- who asked
            question        TEXT NOT NULL,          -- what they asked
            status          TEXT DEFAULT 'pending', -- pending / reminded / resolved
            reminder_sent   INTEGER DEFAULT 0,      -- how many reminders sent to owner
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at     DATETIME
        )
    """)
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
#  SAVE A PENDING QUESTION
# ──────────────────────────────────────────────

def save_pending_question(customer_number: str, question: str) -> str:
    """
    Saves an unanswered customer question to DB.
    Returns the generated pending_id.
    """
    pending_id = uuid.uuid4().hex[:6].upper()   # e.g. "A1B2C3" — short and clean

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO pending_questions
           (id, customer_number, question)
           VALUES (?, ?, ?)""",
        (pending_id, customer_number, question)
    )
    conn.commit()
    conn.close()

    return pending_id


# ──────────────────────────────────────────────
#  TRIGGER FALLBACK — called from owner_clone.py
# ──────────────────────────────────────────────

def trigger_fallback(customer_number: str, question: str):
    """
    Main entry point.
    1. Tells customer we're checking
    2. Notifies owner with the question + pending ID
    3. Saves to DB for scheduler to track

    Called from owner_clone.py when GPT can't answer confidently.
    """

    # ── Step 1: Acknowledge to customer immediately ──
    customer_reply = (
        "Ek second 🙏 Main confirm karke aapko batata/batati hoon.\n"
        "I'll get back to you shortly!"
    )
    send_message(customer_number, customer_reply)

    # ── Step 2: Save to DB ──
    pending_id = save_pending_question(customer_number, question)

    # ── Step 3: Notify owner ──
    owner_alert = build_owner_alert(customer_number, question, pending_id)
    send_message(OWNER_NUMBER, owner_alert)

    print(f"📌 Fallback triggered | ID: {pending_id} | Customer: {customer_number}")
    return pending_id


def build_owner_alert(customer_number: str, question: str, pending_id: str) -> str:
    """
    Builds the WhatsApp message sent to the owner.
    The PENDING_ID is embedded so we can extract it when owner replies.
    Owner must QUOTE/REPLY to this message — bot reads the quoted context.
    """
    return (
        f"❓ *Customer Question*\n\n"
        f"From: +{customer_number}\n"
        f"Question: {question}\n\n"
        f"👆 *Reply to THIS message* to answer them.\n"
        f"Your reply will be forwarded automatically.\n\n"
        f"[REF:{pending_id}]"     # ← This is how we track which question
    )


# ──────────────────────────────────────────────
#  HANDLE OWNER REPLY — called from app.py webhook
# ──────────────────────────────────────────────

def handle_owner_reply(owner_message: str, quoted_message: str) -> bool:
    """
    Called when the owner sends a message that quotes a previous notification.
    Extracts pending_id from the quoted text, finds the customer, forwards reply.

    Args:
        owner_message:  what the owner typed as their reply
        quoted_message: the text of the message they quoted/replied to

    Returns:
        True if successfully handled as a fallback reply
        False if it wasn't a fallback reply (normal owner message)
    """

    # ── Step 1: Extract REF from quoted message ──
    pending_id = extract_pending_id(quoted_message)

    if not pending_id:
        return False    # Not a fallback reply — let normal routing handle it

    # ── Step 2: Look up which customer this belongs to ──
    customer_number = get_customer_for_pending(pending_id)

    if not customer_number:
        send_message(OWNER_NUMBER, f"⚠️ Could not find customer for REF:{pending_id}. They may have already been answered.")
        return True

    # ── Step 3: Forward owner's reply to customer ──
    customer_msg = (
        f"{owner_message}\n\n"
        f"— Team"
    )
    send_message(customer_number, customer_msg)

    # ── Step 4: Mark as resolved in DB ──
    resolve_pending(pending_id)

    # ── Step 5: Confirm to owner ──
    send_message(OWNER_NUMBER, f"✅ Reply forwarded to +{customer_number}")

    print(f"✅ Fallback resolved | ID: {pending_id} | Customer: {customer_number}")
    return True


def extract_pending_id(quoted_text: str) -> str | None:
    """
    Extracts [REF:XXXXXX] from a quoted message string.
    Returns the ID or None if not found.
    """
    import re
    match = re.search(r"\[REF:([A-Z0-9]{6})\]", quoted_text)
    return match.group(1) if match else None


# ──────────────────────────────────────────────
#  SCHEDULER JOB — checks for unanswered questions
# ──────────────────────────────────────────────

def check_pending_fallbacks():
    """
    Called by the scheduler every minute (alongside check_reminders).
    If a question has been pending too long:
      - First timeout: remind owner + update customer
      - Further timeouts: remind owner again only
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Find all pending questions older than the timeout window
    c.execute("""
        SELECT id, customer_number, question, reminder_sent, created_at
        FROM pending_questions
        WHERE status IN ('pending', 'reminded')
        AND datetime(created_at, '+' || ? || ' minutes') < datetime('now')
    """, (FALLBACK_TIMEOUT_MINUTES,))

    overdue = c.fetchall()
    conn.close()

    for row in overdue:
        pending_id, customer_number, question, reminder_sent, created_at = row
        handle_overdue_fallback(pending_id, customer_number, question, reminder_sent)


def handle_overdue_fallback(pending_id, customer_number, question, reminder_sent):
    """Handles a single overdue pending question."""

    if reminder_sent == 0:
        # ── First timeout: remind owner + update customer ──

        # Remind owner
        reminder = (
            f"⏰ *Pending Question — No Reply Yet*\n\n"
            f"From: +{customer_number}\n"
            f"Question: {question}\n\n"
            f"👆 Please *reply to this message* to answer them.\n\n"
            f"[REF:{pending_id}]"
        )
        send_message(OWNER_NUMBER, reminder)

        # Update customer
        customer_update = (
            "Still checking on your question 🙏 "
            "Will get back to you very soon, sorry for the wait!"
        )
        send_message(customer_number, customer_update)

        # Update DB
        update_reminder_count(pending_id, "reminded", 1)

        print(f"⏰ First reminder sent | ID: {pending_id}")

    else:
        # ── Subsequent timeouts: remind owner only ──
        reminder = (
            f"🚨 *Urgent — Customer Still Waiting!*\n\n"
            f"From: +{customer_number}\n"
            f"Question: {question}\n\n"
            f"👆 Reply to this message to answer them.\n\n"
            f"[REF:{pending_id}]"
        )
        send_message(OWNER_NUMBER, reminder)

        update_reminder_count(pending_id, "reminded", reminder_sent + 1)

        print(f"🚨 Follow-up reminder #{reminder_sent + 1} | ID: {pending_id}")


# ──────────────────────────────────────────────
#  DB HELPERS
# ──────────────────────────────────────────────

def get_customer_for_pending(pending_id: str) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT customer_number FROM pending_questions WHERE id = ? AND status != 'resolved'",
        (pending_id,)
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def resolve_pending(pending_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE pending_questions SET status = 'resolved', resolved_at = datetime('now') WHERE id = ?",
        (pending_id,)
    )
    conn.commit()
    conn.close()


def update_reminder_count(pending_id: str, status: str, count: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE pending_questions SET status = ?, reminder_sent = ? WHERE id = ?",
        (status, count, pending_id)
    )
    conn.commit()
    conn.close()


def get_all_pending() -> list:
    """Returns all unresolved questions. Useful for owner dashboard later."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, customer_number, question, reminder_sent, created_at FROM pending_questions WHERE status != 'resolved' ORDER BY created_at ASC"
    )
    rows = c.fetchall()
    conn.close()
    return rows