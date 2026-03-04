import requests
import os

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")



def send_message(to, text):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }

    response = requests.post(url, headers=headers, json=data)
    print("WHATSAPP STATUS:", response.status_code)
    print("WHATSAPP RESPONSE:", response.json())
    
"""
def send_buttons_message(to, task_text):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": f"⏰ {task_text}\nDid you complete it?"
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "complete_task",
                            "title": "✅ Yes"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": "snooze_10",
                            "title": "⏳ Snooze 10 min"
                        }
                    }
                ]
            }
        }
    }

    requests.post(url, headers=headers, json=payload)
"""

    
