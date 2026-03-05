import os
import json
from openai import OpenAI
from menu_manager import (
    search_item_by_name, mark_item_unavailable, mark_item_available,
    update_stock_count, reset_menu, get_full_stock_report
)
from messenger import send_message

client       = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OWNER_NUMBER = os.getenv("OWNER_NUMBER", "919315544065")


# ──────────────────────────────────────────────
#  OWNER MENU COMMAND CLASSIFIER
# ──────────────────────────────────────────────

MENU_UPDATE_PROMPT = """
You are a restaurant menu update interpreter.

The restaurant owner sends casual messages in Hindi, English, or Hinglish
to update their menu. Your job is to understand what they mean and return JSON.

ONLY return JSON. No explanation. No extra text.

Available actions:
- mark_unavailable  → item is finished/sold out
- mark_available    → item is back/available again
- update_stock      → set a specific stock count
- reset_menu        → everything available again (start of day)
- stock_report      → owner wants to see full stock status
- not_menu_update   → this message is not about menu/stock

Return format:
{
  "action": "",
  "item_name": "",    ← cleaned item name in English (e.g. "dal makhani")
  "quantity": null    ← only for update_stock action
}

Examples:

Owner: "dal makhani khatam"
→ {"action": "mark_unavailable", "item_name": "dal makhani", "quantity": null}

Owner: "paneer tikka finish ho gaya"
→ {"action": "mark_unavailable", "item_name": "paneer tikka", "quantity": null}

Owner: "chicken curry back on"
→ {"action": "mark_available", "item_name": "chicken curry", "quantity": null}

Owner: "stock dal makhani 10"
→ {"action": "update_stock", "item_name": "dal makhani", "quantity": 10}

Owner: "sirf 5 gulab jamun bache hain"
→ {"action": "update_stock", "item_name": "gulab jamun", "quantity": 5}

Owner: "menu reset" or "kal ke liye sab available hai"
→ {"action": "reset_menu", "item_name": "", "quantity": null}

Owner: "stock report" or "menu status"
→ {"action": "stock_report", "item_name": "", "quantity": null}

Owner: "remind me to call supplier"
→ {"action": "not_menu_update", "item_name": "", "quantity": null}
"""


def is_menu_update(message: str) -> bool:
    """
    Quick pre-check — does this message look like a menu update?
    Avoids calling GPT for every single owner message.
    Uses keyword matching as a fast gate.
    """
    keywords = [
        "khatam", "finish", "stock", "available", "unavailable",
        "bache", "bacha", "menu", "item", "reset", "report",
        "back on", "sold out", "nahi hai", "ho gaya", "kar do"
    ]
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in keywords)


def handle_owner_menu_update(message: str) -> bool:
    """
    Main entry point. Called from app.py when owner sends a message.

    Returns:
        True  → was a menu update, handled it
        False → not a menu update, let normal routing handle it
    """

    # Fast keyword gate — avoid GPT call if clearly not menu related
    if not is_menu_update(message):
        return False

    # ── Call GPT to classify the update ──
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": MENU_UPDATE_PROMPT},
                {"role": "user",   "content": message}
            ]
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
    except Exception as e:
        print("Menu update GPT error:", e)
        return False

    action    = data.get("action", "not_menu_update")
    item_name = data.get("item_name", "").strip()
    quantity  = data.get("quantity")

    if action == "not_menu_update":
        return False

    # ── Dispatch to correct handler ──
    if action == "reset_menu":
        _handle_reset(message)
        return True

    if action == "stock_report":
        _handle_stock_report()
        return True

    if action in ("mark_unavailable", "mark_available", "update_stock"):
        return _handle_item_update(action, item_name, quantity)

    return False


# ──────────────────────────────────────────────
#  ACTION HANDLERS
# ──────────────────────────────────────────────

def _handle_item_update(action: str, item_name: str, quantity) -> bool:
    """
    Finds the item by name (fuzzy search) and applies the update.
    Handles ambiguous matches by asking owner to clarify.
    """
    if not item_name:
        return False

    matches = search_item_by_name(item_name)

    # ── No match found ──
    if not matches:
        send_message(
            OWNER_NUMBER,
            f"⚠️ '{item_name}' menu mein nahi mila.\n"
            f"Sahi naam type karein ya 'stock report' bhejein."
        )
        return True

    # ── Multiple matches — ask owner to clarify ──
    if len(matches) > 1:
        options = "\n".join([f"• {m['name']} ({m['category']})" for m in matches])
        send_message(
            OWNER_NUMBER,
            f"Kaunsa item?\n\n{options}\n\nPoora naam type karein."
        )
        return True

    # ── Exactly one match — apply update ──
    item = matches[0]

    if action == "mark_unavailable":
        mark_item_unavailable(item["id"])
        send_message(
            OWNER_NUMBER,
            f"✅ *{item['name']}* menu se hata diya.\n"
            f"Customers ko unavailable dikhega.\n\n"
            f"Wapas add karne ke liye:\n'available {item['name']}'"
        )

    elif action == "mark_available":
        mark_item_available(item["id"])
        send_message(
            OWNER_NUMBER,
            f"✅ *{item['name']}* menu par wapas aa gaya! 🎉"
        )

    elif action == "update_stock":
        if quantity is None:
            send_message(OWNER_NUMBER, f"Quantity nahi mili. Try: 'stock {item['name']} 10'")
            return True
        update_stock_count(item["id"], int(quantity))
        status = "✅ Available" if quantity > 0 else "❌ Unavailable (auto)"
        send_message(
            OWNER_NUMBER,
            f"✅ *{item['name']}* stock update!\n"
            f"Stock: {quantity} pieces\n"
            f"Status: {status}"
        )

    return True


def _handle_reset(message: str):
    """Resets entire menu — all items available."""
    reset_menu()
    send_message(
        OWNER_NUMBER,
        "✅ Menu reset! Saare items available mark ho gaye.\n"
        "Naya din, naya menu 🌅\n\n"
        "Jo items finish ho jayein, just message karein:\n"
        "'[item name] khatam'"
    )


def _handle_stock_report():
    """Sends full stock report to owner."""
    report = get_full_stock_report()
    send_message(OWNER_NUMBER, report)
