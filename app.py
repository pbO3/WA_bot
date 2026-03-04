from flask import Flask, request
import os
import json
import pytz
from datetime import datetime
from dotenv import load_dotenv

from database import (
    add_task, get_all_tasks, delete_old_tasks,
    get_active_tasks, mark_done, get_last_asked,
    snooze_task
)
from messenger import send_message
from time_utils import IST, human_time
from ai_intent import extract_intent
from time_parser import parse_time
from owner_clone import get_owner_clone_reply, get_greeting_reply, get_handoff_message

load_dotenv()
delete_old_tasks()

app = Flask(__name__)

# ── Scheduler: only start in main process, not in Gunicorn workers ──
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("RUN_MAIN") == "true":
    from scheduler import start_scheduler
    start_scheduler()

ACCESS_TOKEN     = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID  = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN     = os.getenv("VERIFY_TOKEN")

# ── Owner's personal WhatsApp number (for reminder notifications) ──
OWNER_NUMBER = os.getenv("OWNER_NUMBER", "919315544065")


# ──────────────────────────────────────────────
#  HOME
# ──────────────────────────────────────────────
@app.route("/")
def home():
    return "✅ Owner Clone Bot is running."


# ──────────────────────────────────────────────
#  WEBHOOK VERIFICATION (Meta API handshake)
# ──────────────────────────────────────────────
@app.route("/webhook", methods=["GET"])
def verify():
    verify_token = os.getenv("VERIFY_TOKEN", "").strip()
    mode         = request.args.get("hub.mode")
    token        = request.args.get("hub.verify_token", "").strip()
    challenge    = request.args.get("hub.challenge")

    if mode == "subscribe" and token == verify_token:
        print("✅ Webhook verified")
        return challenge, 200

    return "Verification failed", 403


# ──────────────────────────────────────────────
#  WEBHOOK — receives all incoming WhatsApp messages
# ──────────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    try:
        value = data["entry"][0]["changes"][0]["value"]

        # Ignore non-message events (delivery receipts, read receipts etc.)
        if "messages" not in value:
            return "ok", 200

        msg_obj = value["messages"][0]
        sender  = msg_obj["from"]

        # Extract text safely — ignore media/stickers for now
        if msg_obj["type"] == "text":
            message = msg_obj["text"]["body"].strip()
        else:
            send_message(sender, "Sorry, I can only read text messages right now 😊")
            return "ok", 200

        print(f"📩 Message from {sender}: {message}")

        # ── If owner is replying, check if they're quoting a fallback notification ──
        if sender == OWNER_NUMBER:
            quoted_text = extract_quoted_text(msg_obj)
            if quoted_text:
                from fallback import handle_owner_reply
                handled = handle_owner_reply(message, quoted_text)
                if handled:
                    return "ok", 200    # Fallback reply handled — stop here

        # ── Normal routing ──
        route_message(sender, message)

    except Exception as e:
        print("❌ Webhook error:", e)

    return "ok", 200


def extract_quoted_text(msg_obj: dict) -> str | None:
    """
    Extracts the quoted/replied-to message text from a WhatsApp message object.
    Meta API puts quoted context inside msg_obj["context"]["id"] but the actual
    quoted body comes through in msg_obj["text"]["quoted_text"] in some versions.
    We check both common formats.
    """
    try:
        # Format 1 — quoted_text directly in text object
        quoted = msg_obj.get("text", {}).get("quoted_text")
        if quoted:
            return quoted

        # Format 2 — context block (use message ID to look up — placeholder for now)
        context = msg_obj.get("context", {})
        if context.get("quoted_message"):
            return context["quoted_message"].get("text", {}).get("body")

    except Exception as e:
        print("Quoted text extraction error:", e)

    return None


# ──────────────────────────────────────────────
#  ROUTER — the brain that decides what to do
# ──────────────────────────────────────────────
def route_message(sender: str, message: str):
    """
    Central router. Uses AI to classify the message then
    dispatches to the right handler.

    Two modes:
    - OWNER mode  → sender is the owner → handle personal reminders
    - CUSTOMER mode → sender is a customer → owner clone replies
    """

    is_owner = (sender == OWNER_NUMBER)

    # ── Step 1: Classify the message ──
    try:
        ai_raw      = extract_intent(message)
        intent_data = json.loads(ai_raw)
        print("🧠 Intent:", intent_data)
    except Exception as e:
        print("Intent parse failed:", e)
        intent_data = {"intent": "unknown", "task": "", "time": "", "minutes": None, "language": "english"}

    intent   = intent_data.get("intent", "unknown")
    task     = intent_data.get("task", "")
    time_text = intent_data.get("time", "")
    minutes  = intent_data.get("minutes")
    language = intent_data.get("language", "english")

    # ── Step 2: If owner is messaging → handle personal intents ──
    if is_owner and intent in ("reminder", "snooze", "complete", "list"):
        handle_owner_intent(sender, intent, task, time_text, minutes, language)
        return

    # ── Step 3: All other cases → Owner Clone handles it ──
    handle_customer_intent(sender, message, intent, language)


# ──────────────────────────────────────────────
#  OWNER INTENT HANDLER — personal reminder management
# ──────────────────────────────────────────────
def handle_owner_intent(sender, intent, task, time_text, minutes, language):
    """Handles the owner's personal reminder intents."""

    # ── Set a new reminder ──
    if intent == "reminder":
        if not task or not time_text:
            send_message(sender, "Samajh nahi aaya 😅 Please tell me the task and time clearly.")
            return

        due_time = parse_time(time_text)

        if not due_time:
            send_message(sender, "Time samajh nahi aaya 😅 Try: 'kal shaam 7 baje call karna'")
            return

        add_task(task, due_time)
        send_message(sender, f"✅ Reminder set!\n📝 {task}\n⏰ {human_time(due_time)}")

    # ── Snooze last reminder ──
    elif intent == "snooze" and minutes:
        task_id = get_last_asked()
        if task_id:
            snooze_task(task_id, int(minutes))
            send_message(sender, f"⏳ Snoozed for {minutes} minutes.")
        else:
            send_message(sender, "No active reminder to snooze.")

    # ── Mark complete ──
    elif intent == "complete":
        task_id = get_last_asked()
        if task_id:
            mark_done(task_id)
            send_message(sender, "✅ Task marked complete! Great work 💪")
        else:
            send_message(sender, "No active task found.")

    # ── List all tasks ──
    elif intent == "list":
        handle_list_tasks(sender)


def handle_list_tasks(sender):
    """Formats and sends the task list to the owner."""
    tasks = get_active_tasks()

    if not tasks:
        send_message(sender, "You're all clear 😄 No pending tasks!")
        return

    IST = pytz.timezone("Asia/Kolkata")
    now = datetime.now(IST)

    overdue_section   = ""
    today_section     = ""
    upcoming_section  = ""

    for t in tasks:
        task_id, task_name, due_time, status = t
        readable = human_time(due_time)
        dt = IST.localize(datetime.strptime(due_time, "%Y-%m-%d %H:%M:%S"))

        if dt < now:
            overdue_section  += f"🔴 {task_name} ({readable})\n"
        elif dt.date() == now.date():
            today_section    += f"🟡 {task_name} ({readable})\n"
        else:
            upcoming_section += f"🟢 {task_name} ({readable})\n"

    reply = "📋 Your Tasks:\n\n"
    if overdue_section:  reply += "Overdue:\n"  + overdue_section  + "\n"
    if today_section:    reply += "Today:\n"    + today_section    + "\n"
    if upcoming_section: reply += "Upcoming:\n" + upcoming_section + "\n"
    reply += "Reply 'done' to complete or 'snooze 10' to delay ⏳"

    send_message(sender, reply)


# ──────────────────────────────────────────────
#  CUSTOMER INTENT HANDLER — owner clone replies
# ──────────────────────────────────────────────
def handle_customer_intent(sender, message, intent, language):
    """
    Routes customer messages.
    Most go straight to the owner clone GPT responder.
    Special intents get dedicated handlers.
    """

    # ── Greeting → warm welcome ──
    if intent == "greeting":
        reply = get_greeting_reply(sender, language)
        send_message(sender, reply)

    # ── Human handoff request → notify owner ──
    elif intent == "human_handoff":
        reply = get_handoff_message(language)
        send_message(sender, reply)
        # Alert the owner on their personal number
        notify_owner_of_handoff(sender, message)

    # ── Everything else → Owner Clone GPT ──
    # This covers: customer_query, book_appointment, place_order,
    # payment, cancel, and even unknown messages
    else:
        reply = get_owner_clone_reply(sender, message)
        send_message(sender, reply)

    print(f"✅ Replied to {sender}: {reply[:60]}...")


def notify_owner_of_handoff(customer_number, customer_message):
    """
    Sends the owner a WhatsApp alert when a customer
    explicitly asks to speak to a human.
    """
    alert = (
        f"🚨 Customer wants to talk to you directly!\n\n"
        f"Number: {customer_number}\n"
        f"Last message: {customer_message}\n\n"
        f"Please reply to them manually."
    )
    send_message(OWNER_NUMBER, alert)


# ──────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)