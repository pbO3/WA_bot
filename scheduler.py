from apscheduler.schedulers.background import BackgroundScheduler
from database import get_due_tasks, mark_asked
from messenger import send_message
from time_utils import now_ist
from fallback import check_pending_fallbacks
import os

USER_NUMBER = os.getenv("OWNER_NUMBER", "919315544065")

scheduler = BackgroundScheduler()


def check_reminders():
    """Existing job — checks due tasks and notifies owner."""
    print("🔔 Scheduler: checking reminders...", now_ist())

    tasks = get_due_tasks()

    for task in tasks:
        task_id   = task[0]
        task_text = task[1]

        send_message(
            USER_NUMBER,
            f"⏰ Reminder: {task_text}\n\nDid you complete it?\nReply: yes or snooze 10"
        )
        mark_asked(task_id)


def check_fallbacks():
    """
    New job — checks for pending customer questions that the owner hasn't answered.
    Reminds owner and updates customer if timeout exceeded.
    """
    print("🔍 Scheduler: checking pending fallbacks...", now_ist())
    check_pending_fallbacks()


def start_scheduler():
    """Start scheduler ONLY when explicitly called (not in Gunicorn workers)."""
    if not scheduler.running:

        # ── Job 1: Reminder checker (your existing logic) ──
        scheduler.add_job(
            check_reminders,
            'interval',
            minutes=1,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=120,
            id="reminders"
        )

        # ── Job 2: Fallback question checker (new) ──
        scheduler.add_job(
            check_fallbacks,
            'interval',
            minutes=5,          # Check every 5 min — no need to be as frequent as reminders
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
            id="fallbacks"
        )

        scheduler.start()
        print("✅ Scheduler started — reminders + fallback checker running")