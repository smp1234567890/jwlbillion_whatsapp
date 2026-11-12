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
from whatsapp_service import send_whatsapp_free_text, send_whatsapp_interactive, send_whatsapp_media

logger = logging.getLogger("bot_service")

GREETING_WORDS = {
    "hi", "hello", "hey", "namaste", "namaskar", "kya haal", "kya haal hai", "kaisa hai", "kaise ho",
    "ram ram", "radhe radhe", "jai shri krishna", "pranam", "salaam", "adaab",
    "hi there", "hey there", "heya", "hiya", "howdy", "sup", "yo", "yoo", "yoyoo",
    "good morning", "good afternoon", "good evening", "good night", "start", "menu"
}

GREETING_PHRASES = [
    "hi there", "hey there", "good morning", "good afternoon", "good evening", "good night",
    "kaise ho", "kya haal", "namaste", "help with my order",
    "more info", "more information", "can i get more info", "can i get more info on this",
    "details please", "tell me more", "more details", "product details", "interested in this"
]

ORDER_QUERY_TRIGGERS = [
    "order", "track", "tracking", "status", "where is my order", "parcel", "shipment", "delivery",
    "kaha hai", "kaha pahucha", "kab aayega", "kab milega", "dispatch"
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
    Includes Bestsellers, Today's Offers, Check Price, Live Video, Track Order, and Customer Rep.
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
                "Visit our website: https://jwlbillion.com/\n\n"
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
                    "title": "Shop & Explore",
                    "rows": [
                        {
                            "id": "menu_products_list",
                            "title": "🛍️ All Products",
                            "description": "Which products we have & categories"
                        },
                        {
                            "id": "menu_pendant_sets",
                            "title": "💎 Pendant Set Design",
                            "description": "View trending pendant necklace sets"
                        },
                        {
                            "id": "menu_bestsellers",
                            "title": "🌟 See Bestsellers",
                            "description": "View our top-rated jewelry designs"
                        },
                        {
                            "id": "menu_offers",
                            "title": "🎁 Today's Offers",
                            "description": "Exclusive daily discounts & deals"
                        },
                        {
                            "id": "menu_price_avail",
                            "title": "🏷️ Price & Availability",
                            "description": "Check pricing & stock on designs"
                        },
                        {
                            "id": "menu_live_video",
                            "title": "📹 See On Live Video",
                            "description": "Request a 1-on-1 live video viewing"
                        }
                    ]
                },
                {
                    "title": "Orders & Support",
                    "rows": [
                        {
                            "id": "menu_track_order",
                            "title": "📦 Track My Order",
                            "description": "Live status of recent purchases"
                        },
                        {
                            "id": "menu_request_voice_call",
                            "title": "📞 Request WhatsApp Call",
                            "description": "Allow our team to call you on WhatsApp"
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

        elif sel_id == "menu_products_list":
            text_reply = (
                "🛍️ *JWL Billion Jewelry Collections* 🛍️\n\n"
                "We craft premium, high-quality jewelry across multiple categories:\n\n"
                "• *Pendant Sets & Necklaces* — American diamond & gold-plated\n"
                "• *Chains & Mala* — Classic, box chain, double ball drops\n"
                "• *Earrings & Studs* — Daily wear & bridal designs\n"
                "• *Bangles & Kadas* — Traditional & modern styles\n"
                "• *Bracelets & Anklets* — Elegant charms & luxury links\n"
                "• *Rings* — Adjustable & statement stones\n"
                "• *Healing Crystals & Stones* — Natural energy stones\n\n"
                "🔗 *Explore full catalogue:* https://jwlbillion.com/\n\n"
                "Tell us which category you'd like to see, and we'll share photos & prices right here!"
            )
            res = send_whatsapp_free_text(sender_phone, text_reply, db=db)
            _save_bot_message(db, sender_phone, text_reply, res.get("message_id"))
            return res

        elif sel_id == "menu_pendant_sets":
            shopify_res = fetch_shopify_products(limit=50)
            all_prods = shopify_res.get("products", [])
            pendants = [
                p for p in all_prods
                if "pendant" in p.get("title", "").lower()
                or "pendant" in str(p.get("tags", "")).lower()
                or "necklace" in p.get("title", "").lower()
            ]
            items_to_show = pendants[:4] if pendants else all_prods[:4]

            # Send photo of the first pendant design if available
            if items_to_show and items_to_show[0].get("image_url"):
                p_first = items_to_show[0]
                p_cap = (
                    f"💎 *{p_first['title']}*\n"
                    f"• Price: ₹{float(p_first.get('price') or 0):,.0f}\n"
                    f"• View Design: {p_first.get('product_url') or 'https://jwlbillion.com/'}"
                )
                media_res = send_whatsapp_media(sender_phone, "image", media_url=p_first["image_url"], caption=p_cap, db=db)
                _save_bot_message(
                    db,
                    sender_phone,
                    f"*{p_first['title']}*\nPrice: ₹{float(p_first.get('price') or 0):,.0f}",
                    media_res.get("message_id"),
                    media_url=p_first["image_url"],
                    message_type="image"
                )

            msg = "💎 *JWL Billion Trending Pendant Set Designs* 💎\n\nHere are some of our top pendant designs:\n\n"
            for i, p in enumerate(items_to_show, 1):
                price_val = f"₹{float(p.get('price') or 0):,.0f}"
                msg += f"*{i}. {p['title']}*\n"
                msg += f"• Price: {price_val}\n"
                if p.get("product_url"):
                    msg += f"• Link: {p['product_url']}\n"
                msg += "\n"
            msg += "Explore all pendant sets: https://jwlbillion.com/\n\nWant to see any of these in a live video call or check stock? Just reply here!"
            res = send_whatsapp_free_text(sender_phone, msg, db=db)
            _save_bot_message(db, sender_phone, msg, res.get("message_id"))
            return res

        elif sel_id == "menu_bestsellers" or sel_id == "menu_new_collection":
            shopify_res = fetch_shopify_products(limit=8)
            products = shopify_res.get("products", [])
            if products:
                # Send the first item with photo if available
                first_p = products[0]
                first_img = first_p.get("image_url")
                if first_img:
                    caption_first = (
                        f"🌟 *{first_p['title']}*\n"
                        f"• Price: ₹{float(first_p.get('price') or 0):,.0f}\n"
                        f"• View Design: {first_p.get('product_url') or 'https://jwlbillion.com/'}"
                    )
                    media_res = send_whatsapp_media(sender_phone, "image", media_url=first_img, caption=caption_first, db=db)
                    _save_bot_message(
                        db,
                        sender_phone,
                        f"*{first_p['title']}*\nPrice: ₹{float(first_p.get('price') or 0):,.0f}",
                        media_res.get("message_id"),
                        media_url=first_img,
                        message_type="image"
                    )

                msg = "🌟 *JWL Billion Bestselling Designs* 🌟\n\nHere are our top customer favorites:\n\n"
                for i, p in enumerate(products[:4], 1):
                    price_val = f"₹{float(p.get('price') or 0):,.0f}"
                    msg += f"*{i}. {p['title']}*\n"
                    msg += f"• Price: {price_val}\n"
                    if p.get("product_url"):
                        msg += f"• Link: {p['product_url']}\n"
                    msg += "\n"
                msg += "Explore all bestselling designs at https://jwlbillion.com/collections/all"
            else:
                msg = (
                    "🌟 *JWL Billion Bestsellers*\n\n"
                    "Discover our most loved jewelry designs online:\n"
                    "👉 https://jwlbillion.com/\n\n"
                    "Tell us what style or piece you're looking for, and we'll send designs right away!"
                )
            res = send_whatsapp_free_text(sender_phone, msg, db=db)
            _save_bot_message(db, sender_phone, msg, res.get("message_id"))
            return res

        elif sel_id == "menu_offers":
            text_reply = (
                "🎁 *Today's Exclusive Offers at JWL Billion* 🎁\n\n"
                "• *Flat 7% OFF* on all handcrafted jewelry: Use code *WELCOME*\n"
                "• *Free Express Shipping* on orders above ₹999\n"
                "• Free Luxury Gift Box Packaging included with every order!\n\n"
                "Shop Today's Deals: https://jwlbillion.com/"
            )
            res = send_whatsapp_free_text(sender_phone, text_reply, db=db)
            _save_bot_message(db, sender_phone, text_reply, res.get("message_id"))
            return res

        elif sel_id == "menu_price_avail":
            text_reply = (
                "💎 *Check Price & Stock Availability*\n\n"
                "Please send the *Name*, *Photo*, or *Screenshot* of the design you're interested in.\n\n"
                "Our jewelry consultant will immediately check live stock, purity, and give you the best price!"
            )
            res = send_whatsapp_free_text(sender_phone, text_reply, db=db)
            _save_bot_message(db, sender_phone, text_reply, res.get("message_id"))
            return res

        elif sel_id == "menu_live_video":
            text_reply = (
                "📹 *See On Live Video Call*\n\n"
                "Experience our jewelry up close in real-time before you buy!\n\n"
                "A jewelry consultant will connect with you on WhatsApp Video Call. "
                "Please reply with your *preferred time slot* (e.g. *Today 4 PM*), and we will schedule your live call!"
            )
            res = send_whatsapp_free_text(sender_phone, text_reply, db=db)
            _save_bot_message(db, sender_phone, text_reply, res.get("message_id"))
            return res

        elif sel_id == "menu_request_voice_call":
            # Send native Call Permission Request so user can tap Allow
            clean_p = sender_phone.replace("+", "").replace(" ", "").replace("-", "")
            perm_payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": clean_p,
                "type": "interactive",
                "interactive": {
                    "type": "call_permission_request",
                    "action": {
                        "name": "call_permission_request"
                    },
                    "body": {
                        "text": "Our jewelry support team is ready to call you on WhatsApp. Please tap Allow below to grant voice call permission."
                    }
                }
            }
            try:
                import requests, config
                url = f"https://graph.facebook.com/v21.0/{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
                headers = {
                    "Authorization": f"Bearer {config.WHATSAPP_API_TOKEN}",
                    "Content-Type": "application/json"
                }
                r = requests.post(url, json=perm_payload, headers=headers, timeout=10)
                _save_bot_message(db, sender_phone, "Sent WhatsApp Call Permission Request card", r.json().get("messages", [{}])[0].get("id"))
                return r.json()
            except Exception as e:
                logger.error(f"Error sending call permission via bot: {e}")
                err_text = "We are preparing your call request. A representative will connect with you shortly!"
                res = send_whatsapp_free_text(sender_phone, err_text, db=db)
                _save_bot_message(db, sender_phone, err_text, res.get("message_id"))
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
    # 4. Check for Pendant Sets Inquiry (e.g. "pendant", "pendant set", "pendants")
    # -------------------------------------------------------------
    is_pendant_query = bool(re.search(r"\b(?:pendant|pendants|pendant set|pendant sets)\b", text_clean))
    if is_pendant_query:
        shopify_res = fetch_shopify_products(limit=50)
        all_prods = shopify_res.get("products", [])
        pendants = [
            p for p in all_prods
            if "pendant" in p.get("title", "").lower()
            or "pendant" in str(p.get("tags", "")).lower()
        ]
        items_to_show = pendants[:4] if pendants else all_prods[:4]

        if items_to_show and items_to_show[0].get("image_url"):
            p_first = items_to_show[0]
            p_cap = (
                f"💎 *{p_first['title']}*\n"
                f"• Price: ₹{float(p_first.get('price') or 0):,.0f}\n"
                f"• View Design: {p_first.get('product_url') or 'https://jwlbillion.com/'}"
            )
            media_res = send_whatsapp_media(sender_phone, "image", media_url=p_first["image_url"], caption=p_cap, db=db)
            _save_bot_message(
                db,
                sender_phone,
                f"*{p_first['title']}*\nPrice: ₹{float(p_first.get('price') or 0):,.0f}",
                media_res.get("message_id"),
                media_url=p_first["image_url"],
                message_type="image"
            )

        msg = "💎 *JWL Billion Pendant Sets & Necklaces* 💎\n\nHere are some of our trending designs:\n\n"
        for i, p in enumerate(items_to_show, 1):
            price_val = f"₹{float(p.get('price') or 0):,.0f}"
            msg += f"*{i}. {p['title']}*\n"
            msg += f"• Price: {price_val}\n"
            if p.get("product_url"):
                msg += f"• Link: {p['product_url']}\n"
            msg += "\n"
        msg += "Explore all pendant sets: https://jwlbillion.com/\n\nNeed assistance or live video viewing? We're here to help!"
        res = send_whatsapp_free_text(sender_phone, msg, db=db)
        _save_bot_message(db, sender_phone, msg, res.get("message_id"))
        return res

    # -------------------------------------------------------------
    # 5. Check for Chains Inquiry (e.g. "chains", "show chain", "gold chain")
    # -------------------------------------------------------------
    is_chain_query = bool(re.search(r"\b(?:chain|chains|kanthi|mala|necklace)\b", text_clean))
    if is_chain_query:
        shopify_res = fetch_shopify_products(limit=50)
        all_prods = shopify_res.get("products", [])
        chains = [
            p for p in all_prods
            if "chain" in p.get("title", "").lower()
            or "chain" in str(p.get("tags", "")).lower()
            or "necklace" in p.get("title", "").lower()
        ]
        items_to_show = chains[:4] if chains else all_prods[:4]

        # Send photo of first chain if available
        if items_to_show and items_to_show[0].get("image_url"):
            c_first = items_to_show[0]
            c_cap = (
                f"⛓️ *{c_first['title']}*\n"
                f"• Price: ₹{float(c_first.get('price') or 0):,.0f}\n"
                f"• Link: {c_first.get('product_url') or 'https://jwlbillion.com/'}"
            )
            media_res = send_whatsapp_media(sender_phone, "image", media_url=c_first["image_url"], caption=c_cap, db=db)
            _save_bot_message(
                db,
                sender_phone,
                f"*{c_first['title']}*\nPrice: ₹{float(c_first.get('price') or 0):,.0f}",
                media_res.get("message_id"),
                media_url=c_first["image_url"],
                message_type="image"
            )

        msg = "⛓️ *JWL Billion Chains & Necklaces Collection* ⛓️\n\nHere are some of our popular designs:\n\n"
        for i, p in enumerate(items_to_show, 1):
            price_val = f"₹{float(p.get('price') or 0):,.0f}"
            msg += f"*{i}. {p['title']}*\n"
            msg += f"• Price: {price_val}\n"
            if p.get("product_url"):
                msg += f"• Link: {p['product_url']}\n"
            msg += "\n"
        msg += "Explore all chains & jewellery: https://jwlbillion.com/\n\nNeed help with custom length or live video viewing? Just ask!"
        res = send_whatsapp_free_text(sender_phone, msg, db=db)
        _save_bot_message(db, sender_phone, msg, res.get("message_id"))
        return res

    # -------------------------------------------------------------
    # 6. Check for Designs / Catalog Inquiry (e.g. "design", "designs", "photo", "catalog", "bhejo", "dikhao")
    # -------------------------------------------------------------
    is_design_query = bool(re.search(r"\b(?:design|designs|catalog|photos?|pics?|collection|sample|samples|bhejo|dikhao|dekhao|photo bhejo|design bhejo|tasveer)\b", text_clean))
    if is_design_query:
        shopify_res = fetch_shopify_products(limit=10)
        products = shopify_res.get("products", [])
        if products and products[0].get("image_url"):
            first_p = products[0]
            first_cap = (
                f"✨ *{first_p['title']}*\n"
                f"• Price: ₹{float(first_p.get('price') or 0):,.0f}\n"
                f"• View Design: {first_p.get('product_url') or 'https://jwlbillion.com/'}"
            )
            media_res = send_whatsapp_media(sender_phone, "image", media_url=first_p["image_url"], caption=first_cap, db=db)
            _save_bot_message(
                db,
                sender_phone,
                f"*{first_p['title']}*\nPrice: ₹{float(first_p.get('price') or 0):,.0f}",
                media_res.get("message_id"),
                media_url=first_p["image_url"],
                message_type="image"
            )

        msg = "✨ *JWL Billion Handcrafted Jewelry Designs* ✨\n\nHere are some of our trending designs:\n\n"
        for i, p in enumerate(products[:4], 1):
            price_val = f"₹{float(p.get('price') or 0):,.0f}"
            msg += f"*{i}. {p['title']}*\n"
            msg += f"• Price: {price_val}\n"
            if p.get("product_url"):
                msg += f"• Link: {p['product_url']}\n"
            msg += "\n"
        msg += "Explore our complete catalogue online: https://jwlbillion.com/"
        res = send_whatsapp_free_text(sender_phone, msg, db=db)
        _save_bot_message(db, sender_phone, msg, res.get("message_id"))
        return res

    # -------------------------------------------------------------
    # 6. Check for Greeting, Info Request, or General Help -> Show Interactive Menu
    # -------------------------------------------------------------
    words = [w.strip() for w in re.split(r"[^\w#]+", text_clean) if w.strip()]
    normalized_words = [re.sub(r'(.)\1{1,}', r'\1', w) for w in words]
    is_info_request = any(phrase in text_clean for phrase in [
        "more info", "more information", "can i get more info", "info on this", "details", "jankari"
    ])
    is_greeting = (
        any(w in GREETING_WORDS for w in words)
        or any(nw in GREETING_WORDS for nw in normalized_words)
        or any(phrase in text_clean for phrase in GREETING_PHRASES)
        or text_clean in ["help", "need help", "support", "hi", "hello"]
        or is_info_request
    )

    if (is_greeting and len(words) <= 12) or is_info_request:
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
            f"🔍 We couldn't find an order matching *#{order_num}* in our JWL Billion Store records.\n\n"
            "Please check the order number sent in your confirmation message, or reply with your registered email."
        )


def _save_bot_message(
    db: Optional[Session],
    sender_phone: str,
    text: str,
    msg_id: Optional[str],
    media_url: Optional[str] = None,
    message_type: str = "text"
):
    if not db:
        return
    try:
        chat_entry = models.ChatMessage(
            customer_phone=sender_phone,
            sender_type="AGENT",
            message_type=message_type,
            text=text,
            media_url=media_url,
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
