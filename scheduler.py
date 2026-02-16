from apscheduler.schedulers.background import BackgroundScheduler
from database import get_due_tasks, mark_asked
from messenger import send_message
from time_utils import now_ist
import os

USER_NUMBER = "919315544065"

def check_reminders():
    
    tasks = get_due_tasks()

    for task in tasks:
        task_id = task[0]
        task_text = task[1]

        send_message(
            USER_NUMBER,
            f"⏰ {task_text}\nDid you complete it?\nReply: yes or snooze 10"
        )

        mark_asked(task_id)

scheduler = BackgroundScheduler()

scheduler.add_job(
    check_reminders,
    'interval',
    minutes=1,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=120
)

if os.environ.get("RUN_MAIN") == "true" or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    scheduler.start()
