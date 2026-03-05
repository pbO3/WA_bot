import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ──────────────────────────────────────────────
#  INTENT CLASSIFIER — decides what the message is about
#  Returns structured JSON for the router in app.py
# ──────────────────────────────────────────────

INTENT_CLASSIFIER_PROMPT = """
You are a WhatsApp message intent classifier.

Your ONLY job is to classify the user message and return JSON. No explanation. No extra text.

Available intents:

PERSONAL (owner's own reminders):
- reminder      → user wants to set a new reminder/task
- snooze        → delay the last reminder
- complete      → user completed a task
- list          → user wants to see their reminders

CUSTOMER (someone contacting the business):
- customer_query      → asking about the business (hours, price, location, services)
- book_appointment    → wants to book / schedule / fix a time
- place_order         → wants to order something (food, product, service)
- cancel              → wants to cancel an appointment or order
- payment             → asking about payment / wants to pay
- human_handoff       → frustrated, asking to speak to a real person

GENERAL:
- menu_request        → customer wants to see the menu
- greeting            → hello, hi, hey, namaste, good morning etc
- unknown             → doesn't fit anything above

Return format:
{
  "intent": "",
  "task": "",
  "time": "",
  "minutes": null,
  "language": "english" | "hindi" | "hinglish"
}

Rules:
- If reminder → fill task and time
- If snooze → fill minutes
- If customer_query / book_appointment / place_order → leave task and time as ""
- Always detect language
- Do NOT normalize time. Return full time phrase as user said it.

Examples:

User: remind me to call mom at 7pm today
→ {"intent": "reminder", "task": "call mom", "time": "7pm today", "minutes": null, "language": "english"}

User: kal subah 9 baje meeting hai
→ {"intent": "reminder", "task": "meeting", "time": "kal subah 9 baje", "minutes": null, "language": "hindi"}

User: what are your timings?
→ {"intent": "customer_query", "task": "", "time": "", "minutes": null, "language": "english"}

User: appointment book karni hai
→ {"intent": "book_appointment", "task": "", "time": "", "minutes": null, "language": "hindi"}

User: do you deliver on sundays?
→ {"intent": "customer_query", "task": "", "time": "", "minutes": null, "language": "english"}

User: snooze 15
→ {"intent": "snooze", "task": "", "time": "", "minutes": 15, "language": "english"}
"""


def extract_intent(message: str) -> str:
    """
    Classifies the user message into a structured intent JSON string.
    Always returns a valid JSON string.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": INTENT_CLASSIFIER_PROMPT},
                {"role": "user", "content": message}
            ]
        )
        return response.choices[0].message.content

    except Exception as e:
        print("Intent extraction failed:", e)
        # Safe fallback — treat as unknown
        return json.dumps({
            "intent": "unknown",
            "task": "",
            "time": "",
            "minutes": None,
            "language": "english"
        })
