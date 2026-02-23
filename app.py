from flask import Flask, request
import requests
import os
from dotenv import load_dotenv
from datetime import datetime
from database import add_task, get_all_tasks, delete_old_tasks, get_active_tasks, get_last_asked, snooze_task, mark_done 
import scheduler
from messenger import send_message
from time_utils import IST
from ai_intent import extract_intent
import json
from time_parser import parse_time

import pytz
from time_utils import human_time




load_dotenv()

delete_old_tasks()

app = Flask(__name__)
from scheduler import start_scheduler

start_scheduler()

import os

# Prevent multiple schedulers in Gunicorn workers
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("RUN_MAIN") == "true":
    from scheduler import start_scheduler
    start_scheduler()


ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

print("ENV TEST:", os.getenv("TEST_MESSAGE"))

@app.route("/")
def home():
    return "Check your terminal output"



# -------- webhook verification --------
@app.route("/webhook", methods=["GET"])
def verify():

    verify_token = os.getenv("VERIFY_TOKEN")

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

     # ---- Clean both tokens ----
    if token:
        token = token.strip()

    if verify_token:
        verify_token = verify_token.strip()

    print("SERVER VERIFY TOKEN:", verify_token)
    print("META TOKEN:", token)

    if mode == "subscribe" and token == verify_token:
        print("Webhook verified successfully")
        return challenge, 200

    return "Verification failed", 403



# -------- receiving messages --------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    try:
        value = data["entry"][0]["changes"][0]["value"]

        if "messages" not in value:
            return "ok", 200

        msg_obj = value["messages"][0]
        sender = msg_obj["from"]
        
        intent = None
        task = None
        time_text = None
        minutes = None

        # ---- HANDLE BUTTON CLICK ----
        if msg_obj["type"] == "interactive":
            button_id = msg_obj["interactive"]["button_reply"]["id"]
        
            if button_id == "complete_task":
                intent = "complete"
        
            elif button_id == "snooze_10":
                intent = "snooze"
                minutes = 10
        
            message = ""   # no text to send to AI
        
        # ---- HANDLE NORMAL TEXT ----
        elif msg_obj["type"] == "text":
            message = msg_obj["text"]["body"].lower().strip()
        
        # ---- OTHER TYPES (image, sticker, etc.) ----
        else:
            message = ""

        
        
        if intent is None and message:
            try:
                ai_raw = extract_intent(message)
                print("AI RAW:", ai_raw)
    
                intent_data = json.loads(ai_raw)
    
                intent = intent_data.get("intent")
                task = intent_data.get("task")
                time_text = intent_data.get("time")
                minutes = intent_data.get("minutes")
    
            except Exception as e:
                print("AI failed:", e)


        if intent == "reminder" and task and time_text:

            due_time = parse_time(time_text)

            if not due_time:
                send_message(sender, "I couldn't understand the time 😅. Please tell me like 'tomorrow 7 pm'")
                return "ok", 200

            add_task(task,due_time)
            readable = due_time.strftime("%I:%M %p")
            send_message(sender, f"Got it 👍 I will remind you at {readable}")
            return "ok", 200

        elif intent == "snooze" and minutes:
            task_id = get_last_asked()
            if task_id:
                snooze_task(task_id, int(minutes))
                send_message(sender, f"Snoozed for {minutes} minutes ⏳")
                return "ok", 200

        elif intent == "complete":
            task_id = get_last_asked()
            if task_id:
                mark_done(task_id)
                send_message(sender, "Great! Marked completed ✔️")
                return "ok", 200

            print("User:", message)
        
                    
        elif intent == "list":

            tasks = get_active_tasks()

            if not tasks:
                send_message(sender, "You're free 😄 No pending tasks right now.")
                return "ok", 200

            from datetime import datetime
            import pytz
            from time_utils import human_time

            IST = pytz.timezone("Asia/Kolkata")
            now = datetime.now(IST)

            message = "📋 Here's what you need to do:\n\n"

            overdue_section = ""
            today_section = ""
            upcoming_section = ""

            for t in tasks:
                task_id, task_name, due_time, status = t

                readable = human_time(due_time)

                dt = datetime.strptime(due_time, "%Y-%m-%d %H:%M:%S")
                dt = IST.localize(dt)

                if dt < now:
                    overdue_section += f"🔴 {task_name} ({readable})\n"

                elif dt.date() == now.date():
                    today_section += f"🟡 {task_name} ({readable})\n"

                else:
                    upcoming_section += f"🟢 {task_name} ({readable})\n"

            if overdue_section:
                message += "Overdue:\n" + overdue_section + "\n"

            if today_section:
                message += "Today:\n" + today_section + "\n"

            if upcoming_section:
                message += "Upcoming:\n" + upcoming_section + "\n"

            message += "Reply 'done' after completing or 'snooze 10' to delay ⏳"

            send_message(sender, message)
            return "ok", 200

        



    # ---- ADD COMMAND ----
        if message.startswith("add"):
            try:
                parts = message.split(" ")
                task_text = " ".join(parts[1:-2])
                time_text = parts[-2] + " " + parts[-1]


                
                from datetime import datetime
                due_time = IST.localize(datetime.strptime(time_text, "%d-%m %H:%M"))
                due_time = due_time.replace(year=datetime.now().year)

                add_task(task_text, due_time.strftime("%Y-%m-%d %H:%M"))
                readable = due_time.strftime("%I:%M %p")
                send_message(sender, f"Reminder saved for {readable}")

            except:
                send_message(sender, "Format: add <task> DD-MM HH:MM")

        # ---- LIST COMMAND ----
        elif message == "list":
            tasks = get_all_tasks()

            if len(tasks) == 0:
                send_message(sender, "No tasks saved.")
            else:
                text = "📝 Your Tasks:\n\n"
                for t in tasks:
                    task_id = t[0]
                    task_name = t[1]
                    due_time = t[2]
                    status = t[3]

                    if status == "done":
                        text += f"{task_id}. ~~{task_name}~~ ✅ (completed)\n"

                    elif status == "asked":
                        text += f"{task_id}. {task_name} ⏳ (waiting confirmation)\n"

                    elif status == "snoozed":
                        text += f"{task_id}. {task_name} 🔁 (snoozed till {due_time})\n"

                    else:  # pending
                        text += f"{task_id}. {task_name} ⏰ at {due_time}\n"

                send_message(sender, text)

        elif message == "yes":
          

            task_id = get_last_asked()
            if task_id:
                mark_done(task_id)
                send_message(sender, "Great! Task marked completed ✅")
            else:
                send_message(sender, "No active task to complete.")


        elif message.startswith("snooze"):
            

            parts = message.split()

            if len(parts) == 2 and parts[1].isdigit():

                minutes = int(parts[1])
                task_id = get_last_asked()

                if task_id:
                    snooze_task(task_id, minutes)
                    send_message(sender, f"⏳ Snoozed for {minutes} minutes.")
                else:
                    send_message(sender, "No active reminder found.")

            else:
                send_message(sender, "Use: snooze 10")

        
    except Exception as e:
        print("Webhook error:", e)

    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
