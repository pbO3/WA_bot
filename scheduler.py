from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from database import get_due_tasks, mark_asked

from app import send_message

USER_NUMBER = "919315544065"

def check_reminders():
    print("Scheduler checking...", datetime.now())

    tasks = get_due_tasks()

    for task in tasks:
        task_id = task[0]
        task_text = task[1]

        send_message(USER_NUMBER,
            f"⏰ {task_text}\nDid you complete it?\nReply: yes or snooze 10")

        mark_asked(task_id)


scheduler = BackgroundScheduler()
scheduler.add_job(check_reminders, 'interval', minutes=1)
scheduler.start()
