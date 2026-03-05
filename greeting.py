import os
import requests
from database import get_conversation_history, save_conversation_turn
from messenger import send_message

ACCESS_TOKEN    = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
WA_URL          = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
HEADERS         = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# ── Bakehouse config ──────────────────────────────────────────
BAKEHOUSE_IMAGE_URL = os.getenv(
    "BAKEHOUSE_IMAGE_URL",
    "https://i.imgur.com/your-bakehouse-image.jpg"   # ← Replace with real image URL
)

# Update this daily or pull from a config/DB later
OFFER_OF_THE_DAY = os.getenv(
    "OFFER_OF_THE_DAY",
    "🎉 Today: Buy 1 Get 1 on Pastries (4–6 PM) | 10% off Birthday Cake Pre-orders"
)


# ══════════════════════════════════════════════════════════════
#  OPTION B — IMAGE + LIST MESSAGE  (works right now, no approval)
#
#  Flow:
#  1. Send bakehouse image with caption
#  2. Immediately send List Message with quick options
#  Works within the 24hr session window.
# ══════════════════════════════════════════════════════════════

def send_greeting_option_b(customer_number: str):
    """
    Option B greeting — image followed by interactive list.
    Call this from app.py for all greetings until template is approved.
    """
    history       = get_conversation_history(customer_number)
    is_returning  = len(history) > 0

    # ── Step 1: Send list options first (instant delivery) ──
    _send_welcome_options(customer_number)

    # ── Step 2: Send image with full caption (arrives as follow-up card) ──
    # Image is sent after list so it never blocks or delays the options
    _send_welcome_image(customer_number, is_returning)

    # ── Save to conversation history ──
    save_conversation_turn(customer_number, "user",      "greeting")
    save_conversation_turn(customer_number, "assistant", "sent_greeting_option_b")


def _send_welcome_image(to: str, is_returning: bool):
    """
    Sends the bakehouse image with full info in caption.
    Caption contains: name, tagline, address, hours, today's offer.
    The list message that follows only needs the options — no repetition.
    """

    if is_returning:
        caption = (
            f"Welcome back to *The Hora Bakehouse* 🥐✨\n"
            f"Great to see you again!\n\n"
            f"📍 Hno 1000, Gagan Vihar, New Delhi\n"
            f"⏰ Open 8:00 AM – 10:00 PM · All days\n\n"
            f"🎁 {OFFER_OF_THE_DAY}"
        )
    else:
        caption = (
            f"Welcome to *The Hora Bakehouse* 🥐✨\n"
            f"Premium artisan breads, cakes & pastries — freshly baked daily!\n\n"
            f"📍 Hno 1000, Gagan Vihar, New Delhi\n"
            f"⏰ Open 8:00 AM – 10:00 PM · All days\n\n"
            f"🎁 {OFFER_OF_THE_DAY}"
        )

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {
            "link": BAKEHOUSE_IMAGE_URL,
            "caption": caption
        }
    }

    response = requests.post(WA_URL, headers=HEADERS, json=payload)
    print(f"📸 Image sent to {to}: {response.status_code}")

    # If image fails (bad URL etc), don't crash — list message still goes
    if response.status_code != 200:
        print(f"⚠️  Image send failed: {response.text}")


def _send_welcome_options(to: str):
    """Sends the interactive List Message with quick options."""

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": "🥐 How can we help you today?"
            },
            "body": {
                "text": "Choose an option below 👇"
            },
            "footer": {
                "text": "The Hora Bakehouse · horabakehouse@gmail.com"
            },
            "action": {
                "button": "How can we help?",
                "sections": [
                    {
                        "title": "Quick Options",
                        "rows": [
                            {
                                "id":          "greet_menu",
                                "title":       "🍰 View Menu",
                                "description": "Browse our full menu with prices"
                            },
                            {
                                "id":          "greet_location",
                                "title":       "📍 Location & Hours",
                                "description": "Address, timings & parking info"
                            },
                            {
                                "id":          "greet_custom_cake",
                                "title":       "🎂 Custom Cake Order",
                                "description": "Birthday, wedding & theme cakes"
                            },
                            {
                                "id":          "greet_offers",
                                "title":       "🎁 Today's Offers",
                                "description": "Current deals & discounts"
                            },
                            {
                                "id":          "greet_other",
                                "title":       "💬 Ask Something Else",
                                "description": "Any other question or query"
                            }
                        ]
                    }
                ]
            }
        }
    }

    response = requests.post(WA_URL, headers=HEADERS, json=payload)
    print(f"📋 Welcome options sent to {to}: {response.status_code}")
    if response.status_code != 200:
        print(f"⚠️  Options send failed: {response.text}")
        # Fallback to plain text if interactive fails
        send_message(to,
            "Main aapki kaise madad kar sakta hoon? 😊\n\n"
            "Reply with:\n"
            "1️⃣ Menu\n"
            "2️⃣ Location\n"
            "3️⃣ Custom Cake\n"
            "4️⃣ Offers\n"
            "5️⃣ Other query"
        )


# ══════════════════════════════════════════════════════════════
#  HANDLE GREETING LIST REPLIES
#  Called from app.py handle_list_reply when ID starts with "greet_"
# ══════════════════════════════════════════════════════════════

def handle_greeting_reply(customer_number: str, reply_id: str):
    """
    Routes quick option selections from the greeting list.
    Called from app.py → handle_list_reply()
    """

    if reply_id == "greet_menu":
        # Send the category menu (already built in menu_messages.py)
        from menu_messages import send_category_list
        send_category_list(customer_number)

    elif reply_id == "greet_location":
        _send_location_info(customer_number)

    elif reply_id == "greet_custom_cake":
        _send_custom_cake_info(customer_number)

    elif reply_id == "greet_offers":
        _send_offers(customer_number)

    elif reply_id == "greet_other":
        send_message(
            customer_number,
            "Bilkul! Apna sawaal type karein, main jawab dunga 😊\n"
            "Ask me anything about our bakehouse!"
        )


def _send_location_info(to: str):
    send_message(to,
        "📍 *The Hora Bakehouse*\n\n"
        "Hno 1000, Gagan Vihar, New Delhi\n"
        "Near DAV Public School · Pincode: 110051\n\n"
        "🗺️ Google Maps: https://maps.app.goo.gl/EmFpGvnEkRnTcwey6\n\n"
        "⏰ *Hours:* Mon–Sun, 8:00 AM – 10:00 PM\n"
        "Open all days including weekends 🎉\n\n"
        "🅿️ Two-wheeler & four-wheeler parking available"
    )


def _send_custom_cake_info(to: str):
    send_message(to,
        "🎂 *Custom Cake Orders*\n\n"
        "We make:\n"
        "• Birthday cakes (kids & adult themes)\n"
        "• Wedding & anniversary cakes\n"
        "• Photo cakes & designer theme cakes\n"
        "• Corporate & bulk orders\n\n"
        "⏳ *Lead time:*\n"
        "Custom cakes — 24 to 48 hours notice\n"
        "Wedding cakes — 3 to 5 days advance\n\n"
        "💳 Advance payment required for custom designs\n\n"
        "To place an order, tell me:\n"
        "1. What occasion?\n"
        "2. How many people / what size?\n"
        "3. Any specific design or flavour? 😊"
    )


def _send_offers(to: str):
    send_message(to,
        f"🎁 *Today's Offers*\n\n"
        f"{OFFER_OF_THE_DAY}\n\n"
        "📌 *Ongoing Offers:*\n"
        "• Buy 1 Get 1 on selected pastries (Weekdays 4–6 PM)\n"
        "• 10% off on birthday cake pre-orders\n"
        "• Festive special combos available\n"
        "• Loyalty card program — ask us for details!\n\n"
        "Koi bhi offer ke baare mein poochh sakte hain 😊"
    )


# ══════════════════════════════════════════════════════════════
#  OPTION A — TEMPLATE MESSAGE  (needs Meta approval)
#
#  HOW TO GET THIS APPROVED:
#
#  1. Go to: Meta Business Manager
#     → WhatsApp → Message Templates → Create Template
#
#  2. Template details:
#     Category:  MARKETING
#     Name:      hora_bakehouse_welcome   (lowercase, underscores only)
#     Language:  English
#
#  3. Template structure:
#     HEADER:  Image (upload your bakehouse photo)
#     BODY:    (see TEMPLATE_BODY below)
#     FOOTER:  (see TEMPLATE_FOOTER below)
#     BUTTONS: Quick Reply buttons (see TEMPLATE_BUTTONS below)
#
#  4. Submit for review — usually approved in 24-48 hours
#
#  5. Once approved, set USE_TEMPLATE=true in Railway env vars
#     and the greeting will automatically switch to Option A
# ══════════════════════════════════════════════════════════════

# ── Exact text to paste into Meta Business Manager ──

TEMPLATE_BODY = """Welcome to *The Hora Bakehouse* 🥐✨

Premium artisan breads, cakes & pastries — freshly baked daily!

📍 Gagan Vihar, New Delhi · ⏰ 8AM–10PM daily

How can we help you today?"""

TEMPLATE_FOOTER = "🎉 Today's Offer: Buy 1 Get 1 on Pastries (4–6 PM)"

TEMPLATE_BUTTONS = [
    "🍰 View Menu",
    "🎂 Custom Cake",
    "📍 Location"
]

# Note: WhatsApp template quick reply buttons are limited to 3 max
# and max 20 characters each. The list above fits within limits.


def send_greeting_option_a(customer_number: str, template_name: str = "hora_bakehouse_welcome"):
    """
    Option A — sends the pre-approved template message with image + buttons.
    Only works after Meta approves the template.
    Set USE_TEMPLATE=true in Railway env vars to activate.

    Args:
        customer_number: customer's WhatsApp number
        template_name:   the approved template name from Meta Business Manager
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": customer_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"},
            "components": [
                {
                    # ── Header: the bakehouse image ──
                    "type": "header",
                    "parameters": [
                        {
                            "type": "image",
                            "image": {"link": BAKEHOUSE_IMAGE_URL}
                        }
                    ]
                },
                {
                    # ── Footer: offer of the day ──
                    # Note: footer text in templates is fixed at approval time
                    # To change it dynamically, use body parameter instead
                    "type": "body",
                    "parameters": []   # Body text is fixed in the template
                }
                # Buttons are defined in the template — no parameters needed here
            ]
        }
    }

    response = requests.post(WA_URL, headers=HEADERS, json=payload)
    print(f"📨 Template greeting sent to {customer_number}: {response.status_code}")

    if response.status_code != 200:
        print(f"⚠️  Template send failed: {response.text}")
        # Graceful fallback to Option B if template fails
        print("↩️  Falling back to Option B greeting")
        send_greeting_option_b(customer_number)
    else:
        save_conversation_turn(customer_number, "user",      "greeting")
        save_conversation_turn(customer_number, "assistant", "sent_greeting_option_a")


# ══════════════════════════════════════════════════════════════
#  MASTER GREETING DISPATCHER
#  This is what app.py calls. Automatically picks A or B.
# ══════════════════════════════════════════════════════════════

def send_greeting(customer_number: str):
    """
    Master greeting function called from app.py.
    Checks USE_TEMPLATE env var to decide Option A or B.
    Swap to Option A just by setting USE_TEMPLATE=true on Railway.
    No code changes needed when template gets approved.
    """
    use_template = os.getenv("USE_TEMPLATE", "false").lower() == "true"

    if use_template:
        send_greeting_option_a(customer_number)
    else:
        send_greeting_option_b(customer_number)