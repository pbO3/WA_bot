from apscheduler.schedulers.background import BackgroundScheduler
from database import get_due_tasks, mark_asked
from messenger import send_message
from time_utils import now_ist
import os

USER_NUMBER = "919315544065"

scheduler = BackgroundScheduler()

def check_reminders():
    print("Scheduler checking...", now_ist())

    tasks = get_due_tasks()

    for task in tasks:
        task_id = task[0]
        task_text = task[1]

        send_message(
            USER_NUMBER,
            f"⏰ {task_text}\nDid you complete it?\nReply: yes or snooze 10"
        )

        mark_asked(task_id)



def start_scheduler():
    """Start scheduler ONLY when explicitly called"""
    if not scheduler.running:
        scheduler.add_job(
            check_reminders,
            'interval',
            minutes=1,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=120
        )
        scheduler.start()
        print("✅ Scheduler started")