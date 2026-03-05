import os
import requests
import json
from menu_manager import get_all_categories, get_items_by_category, get_all_available_items

ACCESS_TOKEN    = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

WA_URL = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}


# ──────────────────────────────────────────────
#  SEND CATEGORY LIST
#  Shown first — customer picks a category
# ──────────────────────────────────────────────

def send_category_list(to: str):
    """
    Sends a WhatsApp List Message showing all menu categories.
    Customer taps a category to see its items.

    WhatsApp List Message supports max 10 rows per section.
    """
    categories = get_all_categories()

    if not categories:
        from messenger import send_message
        send_message(to, "Menu abhi available nahi hai. Thodi der mein try karein 🙏")
        return

    rows = [
        {
            "id": f"cat_{cat['id']}",
            "title": cat["name"],
            "description": "Tap to see items"
        }
        for cat in categories
    ]

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": "🍽️ Our Menu"
            },
            "body": {
                "text": "Kaunsi category dekhni hai? Niche se select karein 👇"
            },
            "footer": {
                "text": "Tap any category to see items & prices"
            },
            "action": {
                "button": "View Menu",
                "sections": [
                    {
                        "title": "Categories",
                        "rows": rows
                    }
                ]
            }
        }
    }

    _send(to, payload)


# ──────────────────────────────────────────────
#  SEND ITEMS LIST
#  Shown after customer picks a category
# ──────────────────────────────────────────────

def send_items_list(to: str, category_id: str):
    """
    Sends a WhatsApp List Message showing all items in a category.
    WhatsApp allows max 10 rows per section and max 24 char titles.
    """
    items = get_items_by_category(category_id)

    if not items:
        from messenger import send_message
        send_message(to, "Is category mein abhi koi item available nahi hai 😔\nDusri category try karein?")
        send_category_list(to)
        return

    rows = []
    for item in items:
        veg_icon = "🟢" if item["veg"] else "🔴"
        # WhatsApp title max 24 chars — truncate gracefully
        title = item["name"][:22] if len(item["name"]) > 22 else item["name"]
        rows.append({
            "id": f"item_{item['id']}",
            "title": f"{veg_icon} {title}",
            "description": f"₹{item['price']}"
        })

    # WhatsApp max 10 rows per section — split if needed
    sections = []
    for i in range(0, len(rows), 10):
        sections.append({
            "title": "Available Items",
            "rows": rows[i:i+10]
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": "🍽️ Menu Items"
            },
            "body": {
                "text": "🟢 = Veg  🔴 = Non-Veg\n\nKoi bhi item select karein 👇"
            },
            "footer": {
                "text": "Tap item to select or ask questions"
            },
            "action": {
                "button": "View Items",
                "sections": sections
            }
        }
    }

    _send(to, payload)


# ──────────────────────────────────────────────
#  SEND ITEM DETAIL + ACTION BUTTONS
#  Shown after customer picks an item
# ──────────────────────────────────────────────

def send_item_detail(to: str, item: dict):
    """
    Sends item details with reply buttons:
    [Add to Order] [Back to Menu] [Ask a Question]
    """
    veg_text  = "🟢 Pure Veg" if item["veg"] else "🔴 Non-Veg"

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {
                "type": "text",
                "text": item["name"]
            },
            "body": {
                "text": f"{veg_text}\nPrice: ₹{item['price']}\n\nKya aap yeh order karna chahte hain?"
            },
            "footer": {
                "text": "Select an option below"
            },
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": f"order_{item['id']}", "title": "✅ Add to Order"}},
                    {"type": "reply", "reply": {"id": "back_to_menu",         "title": "🔙 Back to Menu"}},
                    {"type": "reply", "reply": {"id": f"ask_{item['id']}",    "title": "❓ Ask Question"}},
                ]
            }
        }
    }

    _send(to, payload)


# ──────────────────────────────────────────────
#  SEND FULL MENU AS TEXT (fallback)
#  Used when customer asks "full menu" or
#  WhatsApp List Message fails
# ──────────────────────────────────────────────

def send_full_menu_text(to: str):
    """
    Sends the complete menu as formatted text.
    Fallback if interactive messages aren't supported.
    """
    items = get_all_available_items()

    if not items:
        from messenger import send_message
        from messenger import send_message as sm
        sm(to, "Menu abhi available nahi hai 🙏")
        return

    # Group by category
    from collections import defaultdict
    grouped = defaultdict(list)
    cat_names = {}

    for item in items:
        grouped[item["category_id"]].append(item)
        cat_names[item["category_id"]] = item["category_name"]

    menu_text = "🍽️ *Our Menu*\n"
    menu_text += "─────────────────\n"

    for cat_id, cat_items in grouped.items():
        menu_text += f"\n*{cat_names[cat_id]}*\n"
        for item in cat_items:
            icon = "🟢" if item["veg"] else "🔴"
            menu_text += f"{icon} {item['name']} — ₹{item['price']}\n"

    menu_text += "\n─────────────────\n"
    menu_text += "🟢 Veg  🔴 Non-Veg\n"
    menu_text += "Order karne ke liye item ka naam type karein 😊"

    from messenger import send_message
    send_message(to, menu_text)


# ──────────────────────────────────────────────
#  INTERNAL SENDER
# ──────────────────────────────────────────────

def _send(to: str, payload: dict):
    """Internal function to send any WhatsApp API payload."""
    try:
        response = requests.post(WA_URL, headers=HEADERS, json=payload)
        print(f"📤 Menu message to {to}: {response.status_code}")
        if response.status_code != 200:
            print(f"⚠️  Menu send error: {response.text}")
    except Exception as e:
        print(f"❌ Menu send failed: {e}")
