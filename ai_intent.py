import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are a WhatsApp assistant message interpreter.

Your job is to convert the user's message into structured JSON.

You must ONLY return JSON. No explanation.

Available intents:
- reminder  (user wants a new reminder)
- snooze    (delay the last reminder)
- complete  (user finished the task)
- list      (user asking to see reminders)
- unknown   (not related)

Return format:

{
  "intent": "",
  "task": "",
  "time": "",
  "minutes": null
}

Rules:
If user asks reminder → fill task and time.
If snooze → fill minutes.
If completion → intent = complete.
If unclear → intent = unknown.
"""

def extract_intent(message):

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message}
        ]
    )

    return response.choices[0].message.content
