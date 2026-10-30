"""
Bot Service
Handles intelligent conversational auto-replies for inbound WhatsApp customer messages:
1. Greetings ("Hi", "Hello", "Hey") -> Interactive or friendly welcome with options.
2. Order Queries ("Where is my order?", "Order status", "#1001") -> Shopify live fulfillment lookup.
3. Fallback support responses.
"""

import re
import logging
from typing import Optional, Tuple
from sqlalchemy.orm import Session
import models
from services.shopify_service import find_order_by_name_or_id, find_recent_orders_by_phone
from whatsapp_service import send_whatsapp_free_text

logger = logging.getLogger("bot_service")

GREETING_WORDS = {
    "hi", "hello", "hey", "namaste", "kem cho", "kemcho", "halo", "ola",
    "hi there", "hey there", "heya", "hiya", "howdy", "sup", "yo", "yoo", "yoyoo",
    "good morning", "good afternoon", "good evening", "good night"
}

GREETING_PHRASES = [
    "hi there", "hey there", "good morning", "good afternoon", "good evening", "good night", "kem cho"
]

ORDER_QUERY_TRIGGERS = [
    "order", "track", "tracking", "status", "where is my order", "parcel", "shipment", "delivery", "kaha hai", "dispatch"
]


def match_order_number(text: str) -> Optional[str]:
    """
    Finds order patterns like #1001, # 1001, or standalone 4-6 digit order numbers.
    """
    # Pattern 1: Explicit hashtag (e.g. #1024 or # 1024)
    m = re.search(r"#\s*(\d{3,8})", text)
    if m:
        return m.group(1)
    
    # Pattern 2: "order 1024" or "order number 1024"
    m = re.search(r"(?:order|ord|no\.?)\s*(?:id|number|no)?\s*[:#-]?\s*(\d{3,8})", text, re.IGNORECASE)
    if m:
        return m.group(1)
    
    # Pattern 3: Standalone 4 to 6 digits if text is very short
    clean = text.strip()
    if clean.isdigit() and 3 <= len(clean) <= 6:
        return clean
    
    return None


def generate_auto_reply(
    sender_phone: str,
    message_text: str,
    customer_name: Optional[str] = None
) -> Optional[str]:
    """
    Decides whether to auto-reply and generates the appropriate response.
    Returns reply text or None if no auto-reply should trigger.
    """
    text_clean = message_text.strip().lower()
    if not text_clean:
        return None

    words = [w.strip() for w in re.split(r"[^\w#]+", text_clean) if w.strip()]

    # Check for direct order lookup number first
    extracted_order = match_order_number(message_text)
    if extracted_order:
        order = find_order_by_name_or_id(extracted_order)
        if order:
            reply = f"📦 *Order Status for {order['order_number']}*\n\n"
            reply += f"• *Status:* {order['fulfillment_status']}\n"
            reply += f"• *Payment:* {order['financial_status']}\n"
            reply += f"• *Items:* {order['items_summary']}\n"
            reply += f"• *Total:* {order['currency']}{order['total_price']}\n"
            
            if order.get("tracking_number"):
                reply += f"\n🚚 *Courier:* {order.get('tracking_company') or 'Standard Courier'}\n"
                reply += f"📋 *Tracking No:* {order['tracking_number']}\n"
                if order.get("tracking_url"):
                    reply += f"🔗 *Track Live:* {order['tracking_url']}\n"
            else:
                reply += "\n⏳ *Courier Update:* Your package is being packed and prepared for pickup. We will update you with the tracking link once dispatched!"
            return reply
        else:
            return (
                f"🔍 We couldn't find an order matching *#{extracted_order}* in our store records.\n\n"
                "Please double-check the order number sent in your confirmation SMS/Email, or reply with your registered email."
            )

    # Check for order inquiry without number
    is_order_query = any(trigger in text_clean for trigger in ORDER_QUERY_TRIGGERS)
    if is_order_query:
        # Try to look up recent order by phone
        recent_orders = find_recent_orders_by_phone(sender_phone)
        if recent_orders:
            latest = recent_orders[0]
            reply = f"👋 Hello {customer_name or ''}! Found your recent order *{latest['order_number']}*:\n\n"
            reply += f"• *Fulfillment:* {latest['fulfillment_status']}\n"
            reply += f"• *Items:* {latest['items_summary']}\n"
            reply += f"• *Total:* {latest['currency']}{latest['total_price']}\n"
            if latest.get("tracking_number"):
                reply += f"\n🚚 *Courier:* {latest.get('tracking_company') or 'Courier'}\n"
                reply += f"📋 *Tracking No:* {latest['tracking_number']}\n"
                if latest.get("tracking_url"):
                    reply += f"🔗 *Track:* {latest['tracking_url']}\n"
            else:
                reply += "\n⏳ Package is being prepared for dispatch."
            return reply

        return (
            f"👋 Hello {customer_name or ''}!\n\n"
            "To check the live status of your order, please reply with your *Order Number* (for example: *#1024*)."
        )

    # Check for simple greeting (collapsing repeated letters like 'Hiii' / 'hiiiiiii' -> 'hi', 'Heyyy' -> 'hey')
    normalized_words = [re.sub(r'(.)\1{1,}', r'\1', w) for w in words]
    is_greeting = (
        any(w in GREETING_WORDS for w in words)
        or any(nw in GREETING_WORDS for nw in normalized_words)
        or any(phrase in text_clean for phrase in GREETING_PHRASES)
    )
    if is_greeting and len(words) <= 5:
        greeting_name = f" {customer_name}" if customer_name and customer_name != "Customer" and customer_name != "New WhatsApp Lead" else ""
        return (
            f"Hello{greeting_name}! 😊\n"
            "Thank you for reaching out to *JWL Billion*.\n\n"
            "How can we assist you today?\n"
            "• Reply with your *Order Number* (e.g. *#1024*) to track your order\n"
            "• Ask any question and our support team will reply shortly!"
        )

    return None


def handle_inbound_auto_reply(
    sender_phone: str,
    message_text: str,
    customer_name: Optional[str] = None,
    db: Optional[Session] = None
) -> Optional[str]:
    """
    Evaluates inbound customer message and dispatches auto-reply if conditions match.
    Saves the outbound reply in ChatMessage so agents can see the bot's conversation in Live Chat.
    """
    reply_text = generate_auto_reply(sender_phone, message_text, customer_name)
    if not reply_text:
        return None

    try:
        # Send WhatsApp free text message within the active 24-hour customer service window
        res = send_whatsapp_free_text(
            recipient_phone=sender_phone,
            message_text=reply_text,
            sender_user="AI Assistant",
            db=db
        )
        msg_id = res.get("message_id")
        status_str = "SENT" if res.get("status") in ["success", "success_simulated"] else "FAILED"

        # Persist bot reply to ChatMessage so it immediately shows up in Live Chat
        if db:
            chat_entry = models.ChatMessage(
                customer_phone=sender_phone,
                sender_type="AGENT",
                message_type="text",
                text=reply_text,
                meta_message_id=msg_id,
                status=status_str,
                is_read=True
            )
            db.add(chat_entry)

            log_entry = models.MessageLog(
                recipient_phone=sender_phone,
                template_name="auto_reply_bot",
                language="en",
                sender_user="AI Assistant",
                status=status_str,
                meta_message_id=msg_id
            )
            db.add(log_entry)
            db.commit()

        logger.info(f"[Bot Auto-Reply] Sent and recorded for {sender_phone}: {reply_text[:60]}...")
        return reply_text
    except Exception as e:
        logger.error(f"[Bot Auto-Reply] Failed sending reply to {sender_phone}: {e}")
        return None

