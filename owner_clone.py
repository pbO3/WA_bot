import os
import json
from openai import OpenAI
from database import get_conversation_history, save_conversation_turn
from fallback import trigger_fallback

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ──────────────────────────────────────────────
#  OWNER CLONE RESPONDER
#  Loads business profile and replies AS the owner
#  Maintains per-customer conversation history
# ──────────────────────────────────────────────

def load_business_profile() -> str:
    """
    Loads the business profile text file.
    This file is the 'brain' of the owner clone.
    """
    profile_path = os.path.join(os.path.dirname(__file__), "business_profile.txt")
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print("⚠️  business_profile.txt not found! Please create it.")
        return "Business profile not available."


# Load once at module import — not on every message
BUSINESS_PROFILE = load_business_profile()


def build_system_prompt() -> str:
    """
    Builds the owner clone system prompt by injecting the business profile.
    This is what makes the bot sound like the owner — not a generic bot.
    """
    return f"""
You are an AI assistant acting as the owner of a business on WhatsApp.

Your job is to reply to customer messages exactly as the owner would — warm, helpful, and natural.
You are NOT a robot. You are NOT a corporate support agent.
You are the owner personally replying to a customer.

STRICT RULES:
1. ONLY answer based on the business information provided below.
2. If you don't know something (e.g. a specific price not listed), say:
   "Main confirm karke batata/batati hoon" or "Let me check and confirm for you."
3. Never make up prices, timings, or services that are not in the profile.
4. Match the customer's language — if they write in Hindi, reply in Hindi.
   If Hinglish, reply in Hinglish. If English, reply in English.
5. Keep replies SHORT and WhatsApp-friendly. No bullet points. No long paragraphs.
6. Use 1-2 emojis max. Keep it human and warm.
7. If customer wants to book appointment → collect their name + preferred time naturally.
8. If customer wants to order → ask what they'd like and confirm the order clearly.
9. If customer is angry or frustrated → be empathetic, don't be defensive.
10. Never reveal that you are an AI unless directly and sincerely asked.
    If asked, say: "Main AI assistant hoon jo [Owner Name] ki taraf se reply kar raha/rahi hoon."

── BUSINESS PROFILE ──────────────────────────────
{BUSINESS_PROFILE}
──────────────────────────────────────────────────

Remember: You ARE the owner. Reply naturally as they would.
"""


def get_owner_clone_reply(customer_number: str, customer_message: str) -> str:
    """
    Main function — takes customer number + message,
    retrieves their history, calls GPT, saves the turn, returns reply.

    Args:
        customer_number: WhatsApp number of the customer (e.g. "919876543210")
        customer_message: The message they sent

    Returns:
        str: The reply to send back to the customer
    """

    # ── Step 1: Load this customer's conversation history ──
    history = get_conversation_history(customer_number)

    # ── Step 2: Add the new message to history ──
    history.append({"role": "user", "content": customer_message})

    # ── Step 3: Keep last 20 turns to avoid token overflow ──
    # (10 customer messages + 10 bot replies)
    trimmed_history = history[-20:]

    # ── Step 4: Call GPT with business profile as system prompt ──
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.7,       # Slight warmth — owner sounds human, not robotic
            max_tokens=300,        # Keep WhatsApp replies short
            messages=[
                {"role": "system", "content": build_system_prompt()},
                *trimmed_history
            ]
        )

        reply = response.choices[0].message.content.strip()

    except Exception as e:
        print("Owner clone GPT error:", e)
        reply = "Ek second, main abhi busy hoon. Thodi der mein reply karta/karti hoon 🙏"

    # ── Step 5: Save both turns to DB for memory ──
    save_conversation_turn(customer_number, "user", customer_message)
    save_conversation_turn(customer_number, "assistant", reply)

    return reply


def get_greeting_reply(customer_number: str, language: str) -> str:
    """
    Handles greetings — warm, personalised first impression.
    Checks if this is a returning customer or new one.
    """
    history = get_conversation_history(customer_number)
    is_returning = len(history) > 0

    if is_returning:
        if language == "hindi":
            message = "Wapas aaiye! 😊 Kya main aapki madad kar sakta/sakti hoon?"
        else:
            message = "Welcome back! 😊 How can I help you today?"
    else:
        if language == "hindi":
            message = "Namaste! 🙏 Main aapki kaise madad kar sakta/sakti hoon?"
        else:
            message = "Hello! Welcome 😊 How can I help you today?"

    # Save the greeting interaction
    save_conversation_turn(customer_number, "user", "greeting")
    save_conversation_turn(customer_number, "assistant", message)

    return message


def get_handoff_message(language: str) -> str:
    """
    When customer explicitly asks for a human / owner gets alerted.
    """
    if language == "hindi":
        return "Bilkul samajh gaya! Main owner ko abhi alert kar raha/rahi hoon. Thodi der mein wo personally reply karenge 🙏"
    return "Understood! I'm alerting the owner right now. They'll reply to you personally very shortly 🙏"