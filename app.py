from flask import Flask, request
from flask import requests
import os
from dotenv import load_dotenv
from datetime import datetime
from database import add_task, get_all_tasks, delete_old_tasks
import scheduler
from messenger import send_message


load_dotenv()

delete_old_tasks()

app = Flask(__name__)

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

    if mode == "subscribe" and token == verify_token:
        print("Webhook verified successfully")
        return challenge, 200

    return "Verification failed", 403



# -------- receiving messages --------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    try:
        # Check if message exists in webhook payload
        if "messages" not in data["entry"][0]["changes"][0]["value"]:
            return "ok", 200

        message = data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        sender = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
        message = message.lower().strip()

        print("User:", message)

        # ---- ADD COMMAND ----
        if message.startswith("add"):
            try:
                parts = message.split(" ")
                task_text = " ".join(parts[1:-2])
                time_text = parts[-2] + " " + parts[-1]


                from datetime import datetime
                due_time = datetime.strptime(time_text, "%d-%m %H:%M")
                due_time = due_time.replace(year=datetime.now().year)

                add_task(task_text, due_time.strftime("%Y-%m-%d %H:%M"))

                send_message(sender, f"Reminder saved for {due_time}")

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
            from database import mark_done, get_last_asked

            task_id = get_last_asked()
            if task_id:
                mark_done(task_id)
                send_message(sender, "Great! Task marked completed ✅")
            else:
                send_message(sender, "No active task to complete.")

        elif message.startswith("snooze"):
            try:
                minutes = int(message.split()[1])

                from database import snooze_task, get_last_asked
                task_id = get_last_asked()

                if task_id:
                    snooze_task(task_id, minutes)
                    send_message(sender, f"⏰ Snoozed for {minutes} minutes")
                else:
                    send_message(sender, "No task to snooze.")
            except:
                send_message(sender, "Use: snooze 10")

        else:
            send_message(sender, "Send:\nadd <task> DD-MM HH:MM\nor\nlist")

    except Exception as e:
        print("Webhook error:", e)

    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
