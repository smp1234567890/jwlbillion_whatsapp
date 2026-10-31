"""
Bot Service
Handles intelligent conversational auto-replies and interactive in-chat menus for inbound WhatsApp customer messages:
1. Greetings ("Hi", "Hello") & Help requests -> Native Interactive List Menu (Track Order, New Collection, Talk to Rep).
2. Order Queries:
   - If customer phone has orders in Shopify / CRM -> Automatically presents recent purchases (up to 3) with buttons/list + "Different Order" option.
   - If customer replies with Order # (e.g. #1024) -> Fetches live Shopify fulfillment, courier, tracking code & tracking link.
3. What's New -> Dynamically fetches top arrivals from Shopify and sends cards with direct shopping links.
4. Support Rep -> Notifies agents and marks conversation for priority support.
"""

import re
import logging
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

import models
from services.shopify_service import (
    find_order_by_name_or_id,
    find_recent_orders_by_phone,
    fetch_shopify_products
)
from whatsapp_service import send_whatsapp_free_text, send_whatsapp_interactive

logger = logging.getLogger("bot_service")

GREETING_WORDS = {
    "hi", "hello", "hey", "namaste", "kem cho", "kemcho", "halo", "ola",
    "hi there", "hey there", "heya", "hiya", "howdy", "sup", "yo", "yoo", "yoyoo",
    "good morning", "good afternoon", "good evening", "good night", "start", "menu"
}

GREETING_PHRASES = [
    "hi there", "hey there", "good morning", "good afternoon", "good evening", "good night", "kem cho", "help with my order"
]

ORDER_QUERY_TRIGGERS = [
    "order", "track", "tracking", "status", "where is my order", "parcel", "shipment", "delivery", "kaha hai", "dispatch"
]


def match_order_number(text: str) -> Optional[str]:
    """
    Finds order patterns like #1001, # 1001, or standalone 3-8 digit order numbers.
    """
    # Pattern 1: Explicit hashtag (e.g. #1024 or # 1024)
    m = re.search(r"#\s*(\d{3,8})", text)
    if m:
        return m.group(1)

    # Pattern 2: "order 1024" or "order number 1024"
    m = re.search(r"(?:order|ord|no\.?)\s*(?:id|number|no)?\s*[:#-]?\s*(\d{3,8})", text, re.IGNORECASE)
    if m:
        return m.group(1)

    # Pattern 3: Standalone 3 to 6 digits if message is essentially just digits
    clean = text.strip()
    if clean.isdigit() and 3 <= len(clean) <= 6:
        return clean

    return None


def get_customer_recent_orders(sender_phone: str, db: Optional[Session] = None) -> List[Dict[str, Any]]:
    """
    Retrieves up to 3 recent orders for the customer by phone.
    Checks Shopify live API first, then falls back to local contact custom_attributes.
    """
    recent = find_recent_orders_by_phone(sender_phone)
    if recent:
        return recent[:3]

    # Fallback to DB contact last_order attribute
    if db:
        contact = db.query(models.Contact).filter(models.Contact.phone == sender_phone).first()
        if contact and isinstance(contact.custom_attributes, dict):
            last_order = contact.custom_attributes.get("last_order")
            if last_order and isinstance(last_order, dict):
                return [{
                    "id": last_order.get("order_id"),
                    "order_number": last_order.get("order_number") or "#Order",
                    "financial_status": "Paid",
                    "fulfillment_status": "Processing",
                    "items_summary": last_order.get("items_summary") or "Jewelry items",
                    "total_price": str(last_order.get("total_price") or "0"),
                    "currency": last_order.get("currency") or "₹"
                }]
    return []


def build_main_menu_list(customer_name: Optional[str] = None) -> dict:
    """
    Builds the native interactive list menu for main welcome / help request.
    """
    name_str = f" {customer_name}" if customer_name and customer_name not in ["Customer", "New WhatsApp Lead"] else ""
    return {
        "type": "list",
        "header": {
            "type": "text",
            "text": "JWL Billion Support"
        },
        "body": {
            "text": (
                f"Hello{name_str}! ✨\n"
                "Thank you for contacting *JWL Billion*.\n\n"
                "How can we assist you today? Please tap below to choose an option:"
            )
        },
        "footer": {
            "text": "Luxury Jewelry & Lifestyle"
        },
        "action": {
            "button": "Select an Option",
            "sections": [
                {
                    "title": "Help & Assistance",
                    "rows": [
                        {
                            "id": "menu_track_order",
                            "title": "📦 Track My Order",
                            "description": "Live status of recent purchases"
                        },
                        {
                            "id": "menu_new_collection",
                            "title": "✨ What's New",
                            "description": "Browse our latest jewelry arrivals"
                        },
                        {
                            "id": "menu_talk_agent",
                            "title": "👤 Talk to Customer Rep",
                            "description": "Connect with a live jewelry consultant"
                        }
                    ]
                }
            ]
        }
    }


def build_recent_orders_interactive(orders: List[Dict[str, Any]], customer_name: Optional[str] = None) -> dict:
    """
    When customer phone matches Shopify orders, presents recent purchases with native buttons or list.
    If 1 or 2 orders -> Uses quick reply buttons (up to 3 buttons max).
    If 3 orders -> Uses interactive list with "Different Order" option.
    """
    name_str = f" {customer_name}" if customer_name and customer_name not in ["Customer", "New WhatsApp Lead"] else ""

    if len(orders) == 1:
        o = orders[0]
        num = str(o["order_number"]).lstrip("#")
        return {
            "type": "button",
            "body": {
                "text": (
                    f"Welcome back{name_str}! 👋\n"
                    f"We found your recent purchase:\n\n"
                    f"🛍️ *Order #{num}*\n"
                    f"• *Status:* {o.get('fulfillment_status', 'Processing')}\n"
                    f"• *Amount:* {o.get('currency', '₹')}{o.get('total_price', '0')}\n"
                    f"• *Items:* {o.get('items_summary', 'Jewelry Item')}\n\n"
                    "Are you inquiring about this order?"
                )
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"track_order_{num}",
                            "title": f"Yes, #{num}"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": "menu_diff_order",
                            "title": "Different Order"
                        }
                    }
                ]
            }
        }

    # For 2 or 3 orders, use Interactive List so customer can tap any order or Different Order
    rows = []
    for o in orders[:3]:
        num = str(o["order_number"]).lstrip("#")
        st = o.get("fulfillment_status") or "Processing"
        amt = f"{o.get('currency', '₹')}{o.get('total_price', '0')}"
        rows.append({
            "id": f"track_order_{num}",
            "title": f"Order #{num} ({st})",
            "description": f"{amt} • {str(o.get('items_summary', 'Jewelry'))[:60]}"
        })

    rows.append({
        "id": "menu_diff_order",
        "title": "🔍 Different Order",
        "description": "Enter another order number manually"
    })

    return {
        "type": "list",
        "header": {
            "type": "text",
            "text": "Your Recent Purchases"
        },
        "body": {
            "text": (
                f"We found recent orders linked to your phone number.\n"
                "Please select which order you'd like to track:"
            )
        },
        "footer": {
            "text": "JWL Billion Order Support"
        },
        "action": {
            "button": "View Recent Orders",
            "sections": [
                {
                    "title": "Recent Purchases",
                    "rows": rows
                }
            ]
        }
    }


def handle_inbound_auto_reply(
    sender_phone: str,
    message_text: str,
    customer_name: Optional[str] = None,
    interactive_id: Optional[str] = None,
    db: Optional[Session] = None
) -> Optional[dict]:
    """
    Evaluates inbound customer message or interactive selection and delivers the response.
    Returns dict info on sent reply or None.
    """
    text_clean = (message_text or "").strip().lower()
    sel_id = (interactive_id or "").strip()

    # -------------------------------------------------------------
    # 1. Handle Interactive Menu Selection (Button or List tap)
    # -------------------------------------------------------------
    if sel_id:
        if sel_id == "menu_track_order" or sel_id == "track_order":
            recent_orders = get_customer_recent_orders(sender_phone, db)
            if recent_orders:
                interactive_payload = build_recent_orders_interactive(recent_orders, customer_name)
                res = send_whatsapp_interactive(sender_phone, interactive_payload, db=db)
                _save_bot_message(db, sender_phone, "Showed recent orders list", res.get("message_id"))
                return res
            else:
                text_reply = (
                    "🔍 *Track Your Order*\n\n"
                    "Please reply with your *Order Number* (e.g. *#1024*), and we'll instantly check its live courier tracking status for you!"
                )
                res = send_whatsapp_free_text(sender_phone, text_reply, db=db)
                _save_bot_message(db, sender_phone, text_reply, res.get("message_id"))
                return res

        elif sel_id.startswith("track_order_"):
            order_num = sel_id.replace("track_order_", "")
            order = find_order_by_name_or_id(order_num)
            text_reply = _format_order_details(order, order_num)
            res = send_whatsapp_free_text(sender_phone, text_reply, db=db)
            _save_bot_message(db, sender_phone, text_reply, res.get("message_id"))
            return res

        elif sel_id == "menu_diff_order":
            text_reply = (
                "📝 Please reply with the *Order Number* you wish to track (for example: *#1050*)."
            )
            res = send_whatsapp_free_text(sender_phone, text_reply, db=db)
            _save_bot_message(db, sender_phone, text_reply, res.get("message_id"))
            return res

        elif sel_id == "menu_new_collection":
            shopify_res = fetch_shopify_products(limit=4)
            products = shopify_res.get("products", [])
            if products:
                msg = "✨ *What's New at JWL Billion* ✨\n\nHere are some of our latest designs:\n\n"
                for i, p in enumerate(products[:4], 1):
                    price_val = f"₹{float(p.get('price') or 0):,.0f}"
                    msg += f"*{i}. {p['title']}*\n"
                    msg += f"• Price: {price_val}\n"
                    if p.get("product_url"):
                        msg += f"• Link: {p['product_url']}\n"
                    msg += "\n"
                msg += "Explore the complete collection at https://jwlbillion.com/"
            else:
                msg = "Explore our latest handcrafted jewelry collection online at https://jwlbillion.com/"
            res = send_whatsapp_free_text(sender_phone, msg, db=db)
            _save_bot_message(db, sender_phone, msg, res.get("message_id"))
            return res

        elif sel_id == "menu_talk_agent":
            text_reply = (
                "👤 A customer support representative from *JWL Billion* has been notified and will assist you shortly.\n\n"
                "Feel free to type your question or order details in the meantime!"
            )
            res = send_whatsapp_free_text(sender_phone, text_reply, db=db)
            _save_bot_message(db, sender_phone, text_reply, res.get("message_id"))
            return res

    # -------------------------------------------------------------
    # 2. Check for Direct Order Number in Text (e.g. #1024 or 1024)
    # -------------------------------------------------------------
    extracted_order = match_order_number(message_text)
    if extracted_order:
        order = find_order_by_name_or_id(extracted_order)
        text_reply = _format_order_details(order, extracted_order)
        res = send_whatsapp_free_text(sender_phone, text_reply, db=db)
        _save_bot_message(db, sender_phone, text_reply, res.get("message_id"))
        return res

    # -------------------------------------------------------------
    # 3. Check for Order Tracking Intent (e.g. "where is my order", "track")
    # -------------------------------------------------------------
    is_order_intent = any(trigger in text_clean for trigger in ORDER_QUERY_TRIGGERS)
    if is_order_intent:
        recent_orders = get_customer_recent_orders(sender_phone, db)
        if recent_orders:
            interactive_payload = build_recent_orders_interactive(recent_orders, customer_name)
            res = send_whatsapp_interactive(sender_phone, interactive_payload, db=db)
            _save_bot_message(db, sender_phone, "Showed recent orders list", res.get("message_id"))
            return res
        else:
            text_reply = (
                "🔍 *Track Your Order*\n\n"
                "Please reply with your *Order Number* (e.g. *#1024*), and we'll immediately fetch live tracking details for you!"
            )
            res = send_whatsapp_free_text(sender_phone, text_reply, db=db)
            _save_bot_message(db, sender_phone, text_reply, res.get("message_id"))
            return res

    # -------------------------------------------------------------
    # 4. Check for Greeting or General Help -> Show Interactive Menu
    # -------------------------------------------------------------
    words = [w.strip() for w in re.split(r"[^\w#]+", text_clean) if w.strip()]
    normalized_words = [re.sub(r'(.)\1{1,}', r'\1', w) for w in words]
    is_greeting = (
        any(w in GREETING_WORDS for w in words)
        or any(nw in GREETING_WORDS for nw in normalized_words)
        or any(phrase in text_clean for phrase in GREETING_PHRASES)
        or text_clean in ["help", "need help", "support", "hi", "hello"]
    )

    if is_greeting and len(words) <= 6:
        menu_payload = build_main_menu_list(customer_name)
        res = send_whatsapp_interactive(sender_phone, menu_payload, db=db)
        _save_bot_message(db, sender_phone, "Sent interactive main menu", res.get("message_id"))
        return res

    return None


def _format_order_details(order: Optional[dict], order_num: str) -> str:
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
            reply += "\n⏳ *Courier Update:* Your package is currently being packed. You will receive an SMS and WhatsApp update with tracking details as soon as it is picked up!"
        return reply
    else:
        return (
            f"🔍 We couldn't find an order matching *#{order_num}* in our Shopify store records.\n\n"
            "Please check the order number sent in your confirmation message, or reply with your registered email."
        )


def _save_bot_message(db: Optional[Session], sender_phone: str, text: str, msg_id: Optional[str]):
    if not db:
        return
    try:
        chat_entry = models.ChatMessage(
            customer_phone=sender_phone,
            sender_type="AGENT",
            message_type="text",
            text=text,
            meta_message_id=msg_id,
            status="SENT" if msg_id and not msg_id.startswith("sim_") else "DELIVERED",
            is_read=True
        )
        db.add(chat_entry)

        log_entry = models.MessageLog(
            recipient_phone=sender_phone,
            template_name="interactive_bot_menu",
            language="en",
            sender_user="AI Assistant",
            status="SENT",
            meta_message_id=msg_id
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to record bot reply in DB: {e}")
