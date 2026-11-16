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
import os
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

# Master switch to pause or enable the bot auto-reply engine.
# Set ENABLE_BOT_AUTOREPLY=false in .env to disable if needed.
ENABLE_BOT_AUTOREPLY = os.getenv("ENABLE_BOT_AUTOREPLY", "true").lower() in ("true", "1", "yes")

GREETING_WORDS = {
    "hi", "hello", "hey", "namaste", "namaskar", "kya haal", "kya haal hai", "kaisa hai", "kaise ho",
    "ram ram", "radhe radhe", "jai shri krishna", "pranam", "salaam", "adaab",
    "hi there", "hey there", "heya", "hiya", "howdy", "sup", "yo", "yoo", "yoyoo",
    "good morning", "good afternoon", "good evening", "good night", "start", "menu",
    "namasteji", "namaskaram", "kem cho", "kem chho", "shubh prabhat", "shubh ratri", "pranamji"
}

GREETING_PHRASES = [
    "hi there", "hey there", "good morning", "good afternoon", "good evening", "good night",
    "kaise ho", "kya haal", "namaste", "help with my order",
    "more info", "more information", "can i get more info", "can i get more info on this",
    "details please", "tell me more", "more details", "product details", "interested in this",
    "jankari chahiye", "detail bhejo", "details bhejo", "jankari do", "aur batao",
    "order ki jankari", "kya price hai", "price batao", "rate batao", "kimat batao"
]

ORDER_QUERY_TRIGGERS = [
    "order", "track", "tracking", "status", "where is my order", "parcel", "shipment", "delivery",
    "kaha hai", "kaha pahucha", "kab aayega", "kab milega", "dispatch"
]

COD_QUERY_PATTERNS = [
    r"\b(?:cod|cash\s*on\s*delivery)\b",
    r"\b(?:cod\s*(?:ha|hai|he|hoga|milega|available|options?))\b",
    r"\b(?:cash\s*on\s*delivery\s*(?:available|milega|hoga|hai)?)\b",
    r"(?:सीओडी|कैश ऑन डिलीवरी)"
]


def match_order_number(text: str) -> Optional[str]:
    """
    Finds explicit order patterns like #1001, # 1001, or 'order 1024'.
    NOTE: Never treats standalone raw digits (like 5000, 2000, 500) as order numbers,
    as customers frequently send budget amounts, phone numbers, or quantities.
    """
    # Pattern 1: Explicit hashtag (e.g. #1024 or # 1024)
    m = re.search(r"#\s*(\d{3,8})", text)
    if m:
        return m.group(1)

    # Pattern 2: Explicit prefix like "order 1024", "order id 1024", "order no 1024"
    m = re.search(r"\b(?:order|ord)\s*(?:id|number|no\.?|#)?\s*[:#-]?\s*(\d{3,8})\b", text, re.IGNORECASE)
    if m:
        return m.group(1)

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
                            "id": "menu_price_avail",
                            "title": "🏷️ Price & Availability",
                            "description": "Check pricing & stock on designs"
                        }
                    ]
                },
                {
                    "title": "Orders & Support",
                    "rows": [
                        {
                            "id": "menu_request_voice_call",
                            "title": "📞 Request Call",
                            "description": "Allow our team to call you on WhatsApp"
                        },
                        {
                            "id": "menu_talk_agent",
                            "title": "👤 Talk to Consultant",
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


def _select_best_jewelry_photo(product: dict) -> Optional[str]:
    """
    Selects a clean, high-quality jewelry product image.
    Filters out internal measurement/scale photos (e.g. ruler markings, cm grids)
    and prefers real jewelry lifestyle or catalog angles.
    """
    images = product.get("all_images") or product.get("images") or []
    img_urls = []
    for im in images:
        if isinstance(im, dict):
            u = im.get("src")
            if u:
                img_urls.append(u)
        elif isinstance(im, str):
            img_urls.append(im)
    if not img_urls and product.get("image_url"):
        img_urls = [product["image_url"]]
    if not img_urls:
        return None

    clean_photos = []
    for u in img_urls:
        fn = u.split("/")[-1].split("?")[0].lower()
        if any(fn.startswith(pfx) for pfx in [
            "img-20261103-wa0060",
            "img-20261104-wa0007",
            "img-20261104-wa0012",
            "img-20261104-wa0013",
            "img-20261104-wa0018"
        ]):
            continue
        if any(bad in fn for bad in ["scale", "ruler", "measurement", "cm_"]):
            continue
        clean_photos.append(u)

    if clean_photos:
        return clean_photos[0]
    return img_urls[0]


def _match_and_send_product_designs(
    sender_phone: str,
    text_clean: str,
    db: Optional[Session]
) -> Optional[dict]:
    """
    Intelligent category & product discovery engine with full Hindi & Hinglish support:
    1. Understands customer intent across rings, cocktail rings, bracelets, bangles, kadas,
       earrings, jhumkas, necklaces, mangalsutras, chains, malas, anklets, payal, watches,
       pyrite crystals, and men/women collections.
    2. Understands inquiries about specific product names or design details.
    3. Fetches live matching products from the Shopify catalog (195+ items).
    4. Automatically selects clean, high-quality jewelry photos (skipping measurement scales).
    5. Sends jewelry photo + caption, followed by direct links and collection page links.
    """
    category_definitions = [
        {
            "id": "rings",
            "label": "Rings & Cocktail Rings",
            "collection_url": "https://jwlbillion.com/collections/rings",
            "keywords": [
                r"\b(?:rings?|cocktail\s*rings?|finger\s*rings?|anguthi|anguthiyan|anguti|chhalla)\b",
                r"(?:अंगूठी|अंगूठियां|रिंग|कॉकटेल रिंग)"
            ],
            "matcher": lambda p: (
                p.get("product_type") == "Ring"
                or (
                    (
                        bool(re.search(r"\b(?:rings?|anguthi)\b", p.get("title", ""), re.IGNORECASE))
                        or bool(re.search(r"\b(?:rings?|anguthi)\b", (p.get("handle") or "").replace("-", " "), re.IGNORECASE))
                    )
                    and not bool(re.search(r"\b(?:earrings?|ear\s*rings?|jhumk[ai]|balis?)\b", p.get("title", ""), re.IGNORECASE))
                    and p.get("product_type") != "Earrings"
                )
            )
        },
        {
            "id": "bracelets",
            "label": "Bracelets",
            "collection_url": "https://jwlbillion.com/collections/bracelet",
            "keywords": [
                r"\b(?:bracelets?|breslets?|braclet|braclets|breslet|wristlet)\b",
                r"(?:ब्रेसलेट|हाथ का ब्रेसलेट)"
            ],
            "matcher": lambda p: (
                p.get("product_type") == "Bracelet"
                or "bracelet" in p.get("title", "").lower()
                or "bracelet" in (p.get("handle") or "").lower()
            )
        },
        {
            "id": "kadas",
            "label": "Kadas & Cuff Bracelets",
            "collection_url": "https://jwlbillion.com/collections/kada",
            "keywords": [
                r"\b(?:kadas?|kade|kara|karas|cuff\s*bracelets?)\b",
                r"(?:कड़ा|कड़े)"
            ],
            "matcher": lambda p: (
                p.get("product_type") == "Kada"
                or "kada" in p.get("title", "").lower()
                or "kada" in (p.get("handle") or "").lower()
            )
        },
        {
            "id": "bangles",
            "label": "Bangles & Choodi",
            "collection_url": "https://jwlbillion.com/collections/bangle",
            "keywords": [
                r"\b(?:bangles?|banglez|chudi|choodi|choodiyan|chudiya|kangan)\b",
                r"(?:चूड़ी|चूड़ियां|कंगन|बैंगल)"
            ],
            "matcher": lambda p: (
                p.get("product_type") == "Bangle"
                or "bangle" in p.get("title", "").lower()
                or "bangle" in (p.get("handle") or "").lower()
            )
        },
        {
            "id": "earrings",
            "label": "Earrings & Jhumkas",
            "collection_url": "https://jwlbillion.com/collections/earrings",
            "keywords": [
                r"\b(?:earrings?|ear\s*rings?|studs?|jhumkas?|jhumki|balis?|hoops?|dangles?|tops|kaan\s*ke|kaan\s*bali|jhalo|jhalar|jhal)\b",
                r"(?:झुमका|झुमके|बाली|बालियां|इयररिंग|कान के|झाले|झालर)"
            ],
            "matcher": lambda p: (
                p.get("product_type") == "Earrings"
                or any(k in p.get("title", "").lower() for k in ["earring", "stud", "hoop", "jhumka", "bali", "dangle"])
                or "earring" in (p.get("handle") or "").lower()
            )
        },
        {
            "id": "pendant_necklace",
            "label": "Pendant Sets & Necklaces",
            "collection_url": "https://jwlbillion.com/collections/necklace",
            "keywords": [
                r"\b(?:pendants?|pendant\s*sets?|necklaces?|haars?|chokers?|mangalsutras?|chains?|malas?|kanthi|gale\s*ka|haar)\b",
                r"(?:हार|गले का हार|पेंडेंट|मंगलसूत्र|चेन|माला)"
            ],
            "matcher": lambda p: (
                p.get("product_type") in ["Necklace", "Chain", "Jewelry Set"]
                or any(k in p.get("title", "").lower() for k in ["pendant", "necklace", "chain", "mangalsutra", "mala", "set"])
            )
        },
        {
            "id": "anklets",
            "label": "Anklets & Payal",
            "collection_url": "https://jwlbillion.com/collections/anklet",
            "keywords": [
                r"\b(?:anklets?|payals?|pajeb|pair\s*ke|panjeb)\b",
                r"(?:पायल|पाजेब|एंक्लेट|पैर की)"
            ],
            "matcher": lambda p: (
                p.get("product_type") == "Anklet"
                or any(k in p.get("title", "").lower() for k in ["anklet", "payal", "pajeb"])
                or "anklet" in (p.get("handle") or "").lower()
            )
        },
        {
            "id": "healing_crystals",
            "label": "Pyrite & Healing Crystals",
            "collection_url": "https://jwlbillion.com/collections/healing-crystel",
            "keywords": [
                r"\b(?:pyrite|crystal|crystals|turtles?|healing|energy\s*stone|kachhua)\b",
                r"(?:पायराइट|कछुआ|क्रिस्टल)"
            ],
            "matcher": lambda p: (
                p.get("product_type") == "Healing Crystal"
                or any(k in p.get("title", "").lower() for k in ["pyrite", "crystal", "turtle"])
                or "pyrite" in (p.get("handle") or "").lower()
            )
        },
        {
            "id": "mens_collection",
            "label": "Men's Jewelry Collection",
            "collection_url": "https://jwlbillion.com/collections/mens-collection",
            "keywords": [
                r"\b(?:mens?|men|mard|boys?|gents?|gents\s*jewellery)\b",
                r"(?:पुरुष|जेंट्स|लड़कों के लिए)"
            ],
            "matcher": lambda p: (
                "men" in p.get("title", "").lower()
                or "men" in [t.lower() for t in p.get("tags", [])]
                or "mens" in (p.get("handle") or "").lower()
            )
        }
    ]

    matched_categories = []
    for cat in category_definitions:
        for pat in cat["keywords"]:
            if re.search(pat, text_clean, re.IGNORECASE):
                matched_categories.append(cat)
                break

    has_design_intent = bool(re.search(
        r"\b(?:design|designs|catalog|catalogue|photos?|pics?|images?|collection|sample|samples|"
        r"bhejo|dikhao|dekhao|tasveer|photo\s*bhejo|dikha\s*do|bhej\s*do|chahiye|dekhna\s*hai|"
        r"kya\s*hai|price|rate|cost|details?)\b|"
        r"(?:डिजाइन|डिज़ाइन|फोटो|तस्वीर|दिखाओ|भेजो|चाहिए|देखना है|रेट|कीमत)",
        text_clean,
        re.IGNORECASE
    ))

    # Also detect Hindi queries asking for what jewelry we have
    is_general_catalog_ask = bool(re.search(
        r"\b(?:kya\s*kya\s*milta\s*hai|kya\s*kya\s*hai|kya\s*designs\s*hai|products?\s*dikhao|collection\s*dikhao)\b|"
        r"(?:क्या क्या मिलता है|क्या क्या है|सामान दिखाओ|ज्वेलरी दिखाओ)",
        text_clean,
        re.IGNORECASE
    ))

    if not matched_categories and not has_design_intent and not is_general_catalog_ask:
        return None

    shopify_res = fetch_shopify_products(limit=250)
    all_products = shopify_res.get("products", [])
    if not all_products:
        return None

    # Detect if user message is in Hindi or Hinglish
    is_hindi_language = bool(re.search(
        r"[\u0900-\u097F]|(?:bhejo|dikhao|dekhao|chahiye|dekhna|batao|kya|hai|hoga|milega|kitne|kaise|jankari|kripya)",
        text_clean,
        re.IGNORECASE
    ))

    # Case A: User asked for specific categories (e.g. Cocktail rings, bracelets, etc.)
    if matched_categories:
        items_to_send = []
        lead_product = None

        for cat in matched_categories:
            matching_prods = [p for p in all_products if cat["matcher"](p)]
            if matching_prods:
                if not lead_product:
                    lead_product = matching_prods[0]
                for p in matching_prods[:2]:
                    if p not in items_to_send:
                        items_to_send.append((cat, p))

        if not items_to_send:
            items_to_send = [(matched_categories[0], p) for p in all_products[:3]]
            lead_product = all_products[0]

        best_photo = _select_best_jewelry_photo(lead_product)
        if best_photo:
            cap = (
                f"*{lead_product['title']}*\n"
                f"Price: ₹{float(lead_product.get('price') or 0):,.0f}\n"
                f"View Design: {lead_product.get('product_url') or 'https://jwlbillion.com/'}"
            )
            media_res = send_whatsapp_media(sender_phone, "image", media_url=best_photo, caption=cap, db=db)
            _save_bot_message(
                db,
                sender_phone,
                f"*{lead_product['title']}*\nPrice: ₹{float(lead_product.get('price') or 0):,.0f}",
                media_res.get("message_id"),
                media_url=best_photo,
                message_type="image"
            )

        cat_names = " & ".join([c["label"] for c in matched_categories])
        primary_col_url = matched_categories[0].get("collection_url") or "https://jwlbillion.com/"

        if is_hindi_language:
            msg = f"*JWL Billion {cat_names}*\n\n"
            msg += "Aapke liye hamare top trending designs:\n\n"
            for i, (cat_item, p) in enumerate(items_to_send[:4], 1):
                price_val = f"₹{float(p.get('price') or 0):,.0f}"
                msg += f"*{i}. {p['title']}*\n"
                msg += f"Price: {price_val}\n"
                if p.get("product_url"):
                    msg += f"Link: {p['product_url']}\n"
                msg += "\n"
            msg += f"Saare designs dekhne ke liye link par click karein:\n{primary_col_url}\n\n"
            msg += "Kisi aur design ki photo ya video call dekhna ho toh batayein!"
        else:
            msg = f"*JWL Billion {cat_names} Designs*\n\n"
            msg += "Here are the designs you requested:\n\n"
            for i, (cat_item, p) in enumerate(items_to_send[:4], 1):
                price_val = f"₹{float(p.get('price') or 0):,.0f}"
                msg += f"*{i}. {p['title']}*\n"
                msg += f"Price: {price_val}\n"
                if p.get("product_url"):
                    msg += f"Link: {p['product_url']}\n"
                msg += "\n"
            msg += f"Browse all designs in this collection:\n{primary_col_url}\n\n"
            msg += "Need video call viewing or custom sizing? Just reply here!"

        res = send_whatsapp_free_text(sender_phone, msg, db=db)
        _save_bot_message(db, sender_phone, msg, res.get("message_id"))
        return res

    # Case B: Specific product search by words in customer message
    # e.g. "pyrite turtle", "ruby elegance", "american diamond", "multi layer pearl"
    query_words = [w for w in re.split(r"[^\w]+", text_clean) if len(w) >= 3 and w not in [
        "please", "send", "give", "show", "design", "designs", "photo", "bhejo", "dikhao",
        "detail", "details", "price", "rate", "cost", "link", "chahiye", "product", "items"
    ]]
    if query_words:
        scored_products = []
        for p in all_products:
            p_text = f"{p.get('title', '')} {p.get('product_type', '')} {' '.join(p.get('tags', []))}".lower()
            score = sum(1 for qw in query_words if qw in p_text)
            if score >= 1:
                scored_products.append((score, p))
        scored_products.sort(key=lambda x: x[0], reverse=True)

        if scored_products and scored_products[0][0] >= 2:
            matched_p = scored_products[0][1]
            best_photo = _select_best_jewelry_photo(matched_p)
            if best_photo:
                cap = (
                    f"*{matched_p['title']}*\n"
                    f"Price: ₹{float(matched_p.get('price') or 0):,.0f}\n"
                    f"View Design: {matched_p.get('product_url') or 'https://jwlbillion.com/'}"
                )
                media_res = send_whatsapp_media(sender_phone, "image", media_url=best_photo, caption=cap, db=db)
                _save_bot_message(
                    db,
                    sender_phone,
                    f"*{matched_p['title']}*\nPrice: ₹{float(matched_p.get('price') or 0):,.0f}",
                    media_res.get("message_id"),
                    media_url=best_photo,
                    message_type="image"
                )

            if is_hindi_language:
                msg = (
                    f"*{matched_p['title']}*\n\n"
                    f"Price: ₹{float(matched_p.get('price') or 0):,.0f}\n"
                    f"Direct Link: {matched_p.get('product_url') or 'https://jwlbillion.com/'}\n\n"
                    "Delivery: Cash on Delivery & 7 Days Easy Return uplabdh hai.\n"
                    "Full collection: https://jwlbillion.com/"
                )
            else:
                msg = (
                    f"*{matched_p['title']}*\n\n"
                    f"Price: ₹{float(matched_p.get('price') or 0):,.0f}\n"
                    f"Product Link: {matched_p.get('product_url') or 'https://jwlbillion.com/'}\n\n"
                    "Available with Cash on Delivery and 7-day easy returns.\n"
                    "Browse all designs: https://jwlbillion.com/"
                )
            res = send_whatsapp_free_text(sender_phone, msg, db=db)
            _save_bot_message(db, sender_phone, msg, res.get("message_id"))
            return res

    # Case C: Generic design or catalog request
    first_p = all_products[0]
    best_photo = _select_best_jewelry_photo(first_p)
    if best_photo:
        first_cap = (
            f"*{first_p['title']}*\n"
            f"Price: ₹{float(first_p.get('price') or 0):,.0f}\n"
            f"View Design: {first_p.get('product_url') or 'https://jwlbillion.com/'}"
        )
        media_res = send_whatsapp_media(sender_phone, "image", media_url=best_photo, caption=first_cap, db=db)
        _save_bot_message(
            db,
            sender_phone,
            f"*{first_p['title']}*\nPrice: ₹{float(first_p.get('price') or 0):,.0f}",
            media_res.get("message_id"),
            media_url=best_photo,
            message_type="image"
        )

    if is_hindi_language:
        msg = "*JWL Billion Handcrafted Jewelry Designs*\n\nYeh rahe hamare trending jewelry designs:\n\n"
        for i, p in enumerate(all_products[:4], 1):
            price_val = f"₹{float(p.get('price') or 0):,.0f}"
            msg += f"*{i}. {p['title']}*\n"
            msg += f"Price: {price_val}\n"
            if p.get("product_url"):
                msg += f"Link: {p['product_url']}\n"
            msg += "\n"
        msg += "Hamari poori catalogue yahan dekhein: https://jwlbillion.com/\n\nAapko kis category (Rings, Kadas, Bracelets, Haar) me dekhna hai, batayein!"
    else:
        msg = "*JWL Billion Handcrafted Jewelry Designs*\n\nHere are some of our trending designs:\n\n"
        for i, p in enumerate(all_products[:4], 1):
            price_val = f"₹{float(p.get('price') or 0):,.0f}"
            msg += f"*{i}. {p['title']}*\n"
            msg += f"Price: {price_val}\n"
            if p.get("product_url"):
                msg += f"Link: {p['product_url']}\n"
            msg += "\n"
        msg += "Explore our complete catalogue online: https://jwlbillion.com/\n\nPlease tell us which jewelry category you would like to view!"

    res = send_whatsapp_free_text(sender_phone, msg, db=db)
    _save_bot_message(db, sender_phone, msg, res.get("message_id"))
    return res


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
    # Immediate circuit breaker: pause bot auto-reply if disabled
    if not ENABLE_BOT_AUTOREPLY:
        logger.debug(f"[Bot Auto-Reply] Bot is currently paused. Skipping reply to {sender_phone}.")
        return None

    text_clean = (message_text or "").strip().lower()
    sel_id = (interactive_id or "").strip()

    # -------------------------------------------------------------
    # 0. Check for Inbound Customer Image/Photo Message
    # If the customer sends a photo (e.g. of a ring, earring, or screenshot),
    # acknowledge the photo directly instead of dumping generic necklace catalog.
    # -------------------------------------------------------------
    is_photo_message = bool(re.match(r"^\[IMAGE\]", text_clean, re.IGNORECASE) or text_clean == "[image]")
    if is_photo_message:
        photo_reply = (
            "Thank you for sharing the photo! ✨\n\n"
            "Our jewelry consultant is reviewing this design right now and will get back to you with live stock availability, purity, and best pricing shortly."
        )
        res = send_whatsapp_free_text(sender_phone, photo_reply, db=db)
        _save_bot_message(db, sender_phone, photo_reply, res.get("message_id"))
        return res
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
            curated_pendants = [
                {
                    "title": "Ruby Elegance Gold-Plated Jewelry Set",
                    "price": 750,
                    "url": "https://jwlbillion.com/products/ruby-elegance-gold-plated-jewelry-set",
                    "image_url": "https://130-210-23-25.sslip.io/uploads/pendant_1_ruby.jpg"
                },
                {
                    "title": "Royal Pearl Radiance Double-Layer Necklace & Crystal Drop Earrings Set",
                    "price": 1499,
                    "url": "https://jwlbillion.com/products/royal-pearl-radiance-double-layer-necklace-crystal-drop-earrings-set-for-women-elegant-wedding-party-jewellery",
                    "image_url": "https://130-210-23-25.sslip.io/uploads/pendant_2_royal_pearl.jpg"
                },
                {
                    "title": "Elegant Multi-Layer Pearl Jewellery Set for Women",
                    "price": 1499,
                    "url": "https://jwlbillion.com/products/elegant-multi-layer-pearl-bracelet-for-women-gold-tone-floral-statement-jewellery",
                    "image_url": "https://130-210-23-25.sslip.io/uploads/pendant_3_multi_pearl.jpg"
                },
                {
                    "title": "Elegant Gold-Toned Multicolour Stone-Studded Necklace & Earrings",
                    "price": 499,
                    "url": "https://jwlbillion.com/products/elegant-gold-toned-multicolour-stone-studded-necklace-earrings",
                    "image_url": "https://130-210-23-25.sslip.io/uploads/pendant_multicolour_model_5.jpg"
                },
                {
                    "title": "Royal Pearl Radiance Wedding & Party Jewellery Set",
                    "price": 1499,
                    "url": "https://jwlbillion.com/products/royal-pearl-radiance-double-layer-necklace-crystal-drop-earrings-set-for-women-elegant-wedding-party-jewellery",
                    "image_url": "https://130-210-23-25.sslip.io/uploads/pendant_2_royal_pearl.jpg"
                },
                {
                    "title": "Silver Tone Blue Crystal Necklace & Bracelet Jewellery Set",
                    "price": 3099,
                    "url": "https://jwlbillion.com/products/silver-tone-blue-crystal-necklace-bracelet-jewellery-set",
                    "image_url": "https://130-210-23-25.sslip.io/uploads/pendant_6_blue_crystal.jpg"
                }
            ]

            # Send photo of the first featured pendant design with caption
            p_first = curated_pendants[0]
            p_cap = (
                f"💎 *{p_first['title']}*\n"
                f"• Price: ₹{p_first['price']:,}\n"
                f"• View Design: {p_first['url']}"
            )
            media_res = send_whatsapp_media(sender_phone, "image", media_url=p_first["image_url"], caption=p_cap, db=db)
            _save_bot_message(
                db,
                sender_phone,
                f"*{p_first['title']}*\nPrice: ₹{p_first['price']:,}",
                media_res.get("message_id"),
                media_url=p_first["image_url"],
                message_type="image"
            )

            msg = "💎 *JWL Billion Trending Pendant & Necklace Sets* 💎\n\nHere are our 6 handcrafted pendant sets:\n\n"
            for i, p in enumerate(curated_pendants, 1):
                msg += f"*{i}. {p['title']}*\n"
                msg += f"• Price: ₹{p['price']:,}\n"
                msg += f"• Link: {p['url']}\n\n"
            msg += "Explore all pendant sets: https://jwlbillion.com/\n\nNeed assistance with pricing or stock? Just reply here!"
            res = send_whatsapp_free_text(sender_phone, msg, db=db)
            _save_bot_message(db, sender_phone, msg, res.get("message_id"))
            return res

        elif sel_id == "menu_bestsellers" or sel_id == "menu_new_collection":
            curated_bestsellers = [
                {
                    "title": "White Gold Block Bracelet",
                    "price": 570,
                    "url": "https://jwlbillion.com/products/07",
                    "image_url": "https://130-210-23-25.sslip.io/uploads/bestseller_1_bracelet.jpg"
                },
                {
                    "title": "Gold Crystal Huggie Hoop Earrings",
                    "price": 390,
                    "url": "https://jwlbillion.com/products/gold-crystal-huggie-hoop-earrings",
                    "image_url": "https://130-210-23-25.sslip.io/uploads/bestseller_2_earrings.jpg"
                },
                {
                    "title": "Gold & Silver Designer Textured Kada",
                    "price": 570,
                    "url": "https://jwlbillion.com/products/gold-silver-designer-textured-kada",
                    "image_url": "https://130-210-23-25.sslip.io/uploads/bestseller_3_kada.jpg"
                },
                {
                    "title": "Two-Tone Gold & Silver Men’s Kada",
                    "price": 370,
                    "url": "https://jwlbillion.com/products/two-tone-gold-silver-men-s-kada",
                    "image_url": "https://130-210-23-25.sslip.io/uploads/bestseller_4_twotone_kada.jpg"
                }
            ]

            # Send photo of the first bestselling item with caption
            first_p = curated_bestsellers[0]
            caption_first = (
                f"🌟 *{first_p['title']}*\n"
                f"• Price: ₹{first_p['price']:,}\n"
                f"• View Design: {first_p['url']}"
            )
            media_res = send_whatsapp_media(sender_phone, "image", media_url=first_p["image_url"], caption=caption_first, db=db)
            _save_bot_message(
                db,
                sender_phone,
                f"*{first_p['title']}*\nPrice: ₹{first_p['price']:,}",
                media_res.get("message_id"),
                media_url=first_p["image_url"],
                message_type="image"
            )

            msg = "🌟 *JWL Billion Bestselling Designs* 🌟\n\nHere are our top customer favorites:\n\n"
            for i, p in enumerate(curated_bestsellers, 1):
                msg += f"*{i}. {p['title']}*\n"
                msg += f"• Price: ₹{p['price']:,}\n"
                msg += f"• Link: {p['url']}\n\n"
            msg += "Explore all bestselling designs at https://jwlbillion.com/collections/all\n\nNeed help with sizing or orders? Just reply here!"
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
                "👤 A jewelry consultant from *JWL Billion* has been notified and will assist you shortly.\n\n"
                "Feel free to type your question or requirements in the meantime!"
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
    # 4. Check for Product Designs / Category Discovery Intent
    # (Rings, Cocktail Rings, Bracelets, Bangles, Earrings, Necklaces, etc.)
    # -------------------------------------------------------------
    design_match_res = _match_and_send_product_designs(sender_phone, text_clean, db=db)
    if design_match_res:
        return design_match_res

    # -------------------------------------------------------------
    # 4b. Check for COD / Cash on Delivery inquiries (e.g. "cod ha", "cod available?")
    # -------------------------------------------------------------
    is_cod_query = any(re.search(pat, text_clean, re.IGNORECASE) for pat in COD_QUERY_PATTERNS)
    if is_cod_query:
        is_hindi = bool(re.search(r"[\u0900-\u097F]|(?:ha|hai|he|hoga|milega|kya|batao)", text_clean, re.IGNORECASE))
        if is_hindi:
            cod_reply = (
                "Haan ji, JWL Billion par *Cash on Delivery (COD)* uplabdh hai! \n\n"
                "Aap bina kisi advance payment ke order place kar sakte hain. "
                "Saath hi hum *7 Days Easy Return & Exchange* policy dete hain.\n\n"
                "Aapko kaun sa design pasand aaya hai? Batayein, hum direct order link bhej denge: https://jwlbillion.com/"
            )
        else:
            cod_reply = (
                "Yes, *Cash on Delivery (COD)* is available across India at JWL Billion! \n\n"
                "You can pay conveniently upon delivery. We also offer *7 Days Easy Returns & Exchanges*.\n\n"
                "Which jewelry design would you like to order? Browse our full catalogue here: https://jwlbillion.com/"
            )
        res = send_whatsapp_free_text(sender_phone, cod_reply, db=db)
        _save_bot_message(db, sender_phone, cod_reply, res.get("message_id"))
        return res

    # -------------------------------------------------------------
    # 5. Check for Greeting, Info Request, or General Help -> Show Interactive Menu
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
