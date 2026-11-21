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


def is_global_autoreply_enabled(db: Optional[Session] = None) -> bool:
    """
    Checks if AI auto-reply is globally enabled.
    Prioritizes dynamic DB SystemSetting 'ai_autoreply_enabled'.
    If not set in DB, falls back to ENABLE_BOT_AUTOREPLY from env.
    """
    if db:
        try:
            setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "ai_autoreply_enabled").first()
            if setting is not None:
                return str(setting.value).strip().lower() in ["true", "1", "yes", "on"]
        except Exception as e:
            logger.debug(f"[Bot Auto-Reply] Could not query ai_autoreply_enabled setting: {e}")
    return ENABLE_BOT_AUTOREPLY

GREETING_WORDS = {
    "hi", "hello", "hey", "namaste", "namasta", "namaskar", "namaskaram", "kya haal", "kya haal hai", "kaisa hai", "kaise ho",
    "ram ram", "radhe radhe", "jai shri krishna", "pranam", "salaam", "adaab",
    "hi there", "hey there", "heya", "hiya", "howdy", "sup", "yo", "yoo", "yoyoo",
    "good morning", "good afternoon", "good evening", "good night", "start", "menu",
    "namasteji", "kem cho", "kem chho", "shubh prabhat", "shubh ratri", "pranamji"
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
    "track order", "track my order", "where is my order", "kaha hai mera order", "kaha pahucha",
    "kab aayega", "kab milega", "dispatch kab hoga", "tracking link", "order tracking", "parcel status",
    "delivery status", "order status"
]

SUPPORT_ESCALATION_PATTERNS = [
    r"\b(?:customer\s*support|customer\s*care|support\s*team|talk\s*to\s*(?:an?\s*)?(?:agent|human|representative|support|person)|human\s*support|live\s*agent|connect\s*(?:me\s*)?(?:to\s*)?(?:agent|human|support)|speak\s*to\s*(?:an?\s*)?(?:agent|human|support))\b",
    r"\b(?:helpdesk|call\s*me|complaint|issue\s*with\s*(?:order|delivery|item|parcel))\b",
    r"\b(?:in\s*transit|transit\s*for|delayed|not\s*delivered|havent\s*received|haven['’]t\s*received|abhy\s*tak\s*nahi\s*mila|abhi\s*tak\s*nahi\s*mila|nahi\s*pahucha|parcel\s*nahi\s*aaya|late\s*ho\s*gaya|refund|return\s*request|exchange\s*request)\b"
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
                r"\b(?:bangles?|banglez|chudi|choodi|choodiyan|chudiya|kangan|bangals?|bangels?)\b",
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
                r"\b(?:earrings?|ear\s*rings?|studs?|jhumkas?|jhumki|balis?|hoops?|dangles?|tops|kaan\s*ke|kaan\s*bali|jhalo|jhalar|jhal|ear?nings?|e?rings?|erring|earings?)\b",
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
                r"\b(?:pendants?|pendant\s*sets?|necklaces?|haars?|chokers?|mangalsutras?|chains?|chainke|chen|chene|chenke|malas?|kanthi|gale\s*ka|haar)\b",
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
                (
                    any(re.search(r"\b(?:men|mens|gents|boys?)\b", t, re.I) for t in p.get("tags", []))
                    or bool(re.search(r"\b(?:men|mens|gents|boys?)\b", p.get("title", ""), re.I))
                    or bool(re.search(r"\b(?:men|mens|gents|boys?)\b", p.get("handle") or "", re.I))
                )
                and not (
                    (
                        bool(re.search(r"\b(?:women|womens|ladies|girls?)\b", p.get("title", ""), re.I))
                        or any(re.search(r"\b(?:women|womens|ladies|girls?)\b", t, re.I) for t in p.get("tags", []))
                    )
                    and not bool(re.search(r"\b(?:men|mens|gents|boys?)\b", p.get("title", ""), re.I))
                )
            )
        }
    ]

    # Pre-process & normalize common Hinglish & phonetic typos before keyword matching
    normalized_query = text_clean
    TYPO_NORMALIZATION = [
        # Bangles & Kadas
        (r'\b(?:banga?ls?|bange?ls?|chud[iy]a?n?|chood[iy]a?n?|kangan)\b', 'bangles'),
        # Earrings & Jhumkas
        (r'\b(?:ear?nings?|e?rings?|erring|earings?|ering|earng|jhumk[ai]|balis?)\b', 'earrings'),
        # Chains & Necklaces
        (r'\b(?:chains?|chainke|chen|chene|chenke|chainka)\b', 'chain'),
        (r'\b(?:pendant|pendent|pendet|pandat|pandet)\b', 'pendant'),
        # Bracelets
        (r'\b(?:breslet|bracelete?|braclet|wristlet)\b', 'bracelet'),
        # Rings
        (r'\b(?:anguthi|anguti|angoothi|chhalla)\b', 'ring'),
        # Intent terms
        (r'\b(?:dijan|dizain|dizine|dizayn|dezign)\b', 'design'),
        (r'\b(?:pp|price|rate|cost|kimat)\b', 'price'),
        (r'\b(?:bheji?y?e?|bhej\s*do|bhejo|dikha?o?|dekha?o?|dikhaye?)\b', 'dikhao'),
    ]
    for pat, rep in TYPO_NORMALIZATION:
        normalized_query = re.sub(pat, rep, normalized_query, flags=re.IGNORECASE)

    matched_categories = []
    for cat in category_definitions:
        for pat in cat["keywords"]:
            if re.search(pat, normalized_query, re.IGNORECASE) or re.search(pat, text_clean, re.IGNORECASE):
                matched_categories.append(cat)
                break

    has_design_intent = bool(re.search(
        r"\b(?:design|designs|catalog|catalogue|photos?|pics?|images?|collection|sample|samples|"
        r"bhejo|dikhao|dekhao|tasveer|photo\s*bhejo|dikha\s*do|bhej\s*do|chahiye|dekhna\s*hai|"
        r"kya\s*hai|price|rate|cost|details?)\b|"
        r"(?:डिजाइन|डिज़ाइन|फोटो|तस्वीर|दिखाओ|भेजो|चाहिए|देखना है|रेट|कीमत)",
        text_clean,
        re.IGNORECASE
    )) or bool(re.search(
        r"\b(?:design|photo|pic|dikhao|bhejo|chahiye|dekhna)\b",
        normalized_query,
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

    # Case A: User asked for specific categories (e.g. Bangles, Chains, Earrings, etc.)
    if matched_categories:
        items_to_send = []
        lead_product = None

        # Check if user specified a gender/audience constraint alongside jewelry type (e.g. "mens bracelet")
        gender_cats = [c for c in matched_categories if c["id"] == "mens_collection"]
        type_cats = [c for c in matched_categories if c["id"] != "mens_collection"]

        # Human Consultative Behavior: Only ask for gender on truly unisex-ambiguous categories (like rings, kadas)
        # For earrings or bangles or necklaces, women is the standard default unless specified
        UNISEX_GENDER_AMBIGUOUS_TYPES = {"rings", "kadas"}
        needs_gender_clarification = any(c["id"] in UNISEX_GENDER_AMBIGUOUS_TYPES for c in type_cats)

        has_explicit_gender = bool(gender_cats) or bool(re.search(
            r"\b(?:men|mens|male|mard|boys?|gents?|women|womens|female|aurat|girls?|ladies|mahila|wife|girlfriend|gf|husband|bhai|sister|behen|maa|mom)\b",
            text_clean,
            re.IGNORECASE
        ))

        if needs_gender_clarification and not has_explicit_gender:
            # Delegate to Qwen to ask whether it is for Men or Women
            return None

        # Check if user requested a specific style/finish (e.g. silver, gold, diamond)
        requested_silver = bool(re.search(r"\b(?:silver|chandi|rupeya)\b", text_clean, re.IGNORECASE))
        requested_gold = bool(re.search(r"\b(?:gold|sona|sone)\b", text_clean, re.IGNORECASE))

        def matches_style(p, silver_req=requested_silver, gold_req=requested_gold):
            if not silver_req and not gold_req:
                return True
            p_text = f"{p.get('title', '')} {' '.join(p.get('tags', []))}".lower()
            if silver_req:
                return bool(re.search(r"\bsilver\b", p_text))
            if gold_req:
                return bool(re.search(r"\bgold\b", p_text))
            return True

        if gender_cats and type_cats:
            gender_matcher = gender_cats[0]["matcher"]
            # Prioritize intersection: products matching BOTH the category and gender
            all_intersect = [p for p in all_products if any(tc["matcher"](p) for tc in type_cats) and gender_matcher(p)]
            styled_intersect = [p for p in all_intersect if matches_style(p)]

            if requested_silver and not styled_intersect and all_intersect:
                # Store does not have silver in this specific category for men/women (e.g. men's silver necklace)
                # Honestly inform the customer and suggest available alternatives (e.g. gold necklaces or silver kadas/bracelets)
                type_label = type_cats[0]["label"].lower()
                alt_silver_prods = [p for p in all_products if gender_matcher(p) and matches_style(p, silver_req=True, gold_req=False)]
                
                if is_hindi_language:
                    no_stock_msg = (
                        f"Filhal hamare paas men's {type_label} sirf premium *Gold-Plated* finish mein available hain, "
                        f"silver-finish mein available nahi hain.\n\n"
                    )
                    if alt_silver_prods:
                        no_stock_msg += "Silver-finish mein hamare paas Men's Kadas & Bracelets hain. Kya aap gold-plated chains dekhna chahenge ya silver bracelets?"
                    else:
                        no_stock_msg += "Kya aap hamare gold-plated designs dekhna chahenge?"
                else:
                    no_stock_msg = (
                        f"Currently, our men's {type_label} are available exclusively in premium *Gold-Plated* finish (we do not have them in silver-finish right now).\n\n"
                    )
                    if alt_silver_prods:
                        no_stock_msg += "However, we do have Men's Kadas and Bracelets in *Silver-Finish*. Would you like to see our gold chains or explore our silver bracelets?"
                    else:
                        no_stock_msg += "Would you like to explore our gold-plated designs instead?"

                res = send_whatsapp_free_text(sender_phone, no_stock_msg, db=db)
                _save_bot_message(db, sender_phone, no_stock_msg, res.get("message_id"))
                return res

            target_prods = styled_intersect if styled_intersect else all_intersect
            if target_prods:
                lead_product = target_prods[0]
                for p in target_prods[:4]:
                    items_to_send.append((type_cats[0], p))
                matched_categories = [type_cats[0]]  # Narrow display collection to the specific type

        if not items_to_send:
            for cat in matched_categories:
                matching_prods = [p for p in all_products if cat["matcher"](p) and matches_style(p)]
                if matching_prods:
                    if not lead_product:
                        lead_product = matching_prods[0]
                    for p in matching_prods[:2]:
                        if p not in items_to_send:
                            items_to_send.append((cat, p))

        if not items_to_send:
            fallback_prods = [p for p in all_products if matches_style(p)]
            if not fallback_prods:
                fallback_prods = all_products
            items_to_send = [(matched_categories[0], p) for p in fallback_prods[:3]]
            lead_product = fallback_prods[0]

        best_photo = _select_best_jewelry_photo(lead_product)
        if best_photo:
            cap = (
                f"*{lead_product['title']}*\n"
                f"Price: ₹{float(lead_product.get('price') or 0):,.0f}\n"
                f"Link: {lead_product.get('product_url') or 'https://jwlbillion.com/'}"
            )
            media_res = send_whatsapp_media(sender_phone, "image", media_url=best_photo, caption=cap, db=db)
            _save_bot_message(
                db,
                sender_phone,
                cap,
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
            msg += "Kisi aur design ki photo dekhni ho ya koi sawal ho toh batayein!"
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
            msg += "Need help with sizing or any product questions? Just reply here!"

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

    # Case C: Generic design or catalog request without any category match
    # Do NOT dump product #0 (pendant). Instead, delegate to Qwen AI so it reads full conversation context and provides an accurate, personalized recommendation!
    return None


def handle_inbound_auto_reply(
    sender_phone: str,
    message_text: str,
    customer_name: Optional[str] = None,
    interactive_id: Optional[str] = None,
    channel: Optional[str] = "general",
    phone_number_id: Optional[str] = None,
    api_token: Optional[str] = None,
    db: Optional[Session] = None
) -> Optional[dict]:
    """
    Evaluates inbound customer message or interactive selection and delivers the response.
    Returns dict info on sent reply or None.
    """
    # Immediate circuit breaker: pause bot auto-reply if globally disabled
    if not is_global_autoreply_enabled(db):
        logger.info(f"[Bot Auto-Reply] Global AI auto-reply is paused. 100% fallback to human for {sender_phone}.")
        return None

    # Check if AI / auto-replies are disabled specifically for this customer
    if db and sender_phone:
        try:
            from models import Contact
            clean_p = sender_phone.replace("+", "").strip()
            contact = db.query(Contact).filter(
                Contact.phone.in_([sender_phone, clean_p, f"+{clean_p}"])
            ).first()
            if contact and isinstance(contact.custom_attributes, dict):
                if contact.custom_attributes.get("ai_disabled"):
                    logger.info(f"[Bot Auto-Reply] AI auto-reply is disabled for customer {sender_phone}. Skipping.")
                    return None
        except Exception as e:
            logger.warning(f"[Bot Auto-Reply] Error checking customer ai_disabled status: {e}")

    text_clean = (message_text or "").strip().lower()
    sel_id = (interactive_id or "").strip()

    # Conversational Context Recovery: If customer sends a short qualifier (e.g. 'mens', 'women', 'gold', 'silver')
    # in response to the bot's qualifying question, collect ALL accumulated attributes (product, gender, metal) from recent conversation
    QUALIFIER_PATTERNS = [
        r"^\s*(?:men|mens|male|mard|boys?|gents?)\s*$",
        r"^\s*(?:women|womens|female|aurat|girls?|ladies|mahila)\s*$",
        r"^\s*(?:gold|silver|diamond|rose\s*gold|ad|cz)\s*$",
        r"^\s*(?:for\s+men|for\s+women|for\s+ladies|for\s+gents|for\s+him|for\s+her)\s*$",
        r"^\s*(?:men\s*k[ae]|women\s*k[ae]|ladies\s*k[ae]|gents\s*k[ae])\s*$"
    ]
    PRODUCT_TERMS = [
        r"\b(?:rings?|anguthi|angoothi)\b",
        r"\b(?:bracelets?|bracelete?|breslets?|breslete?|braclets?|wristlets?)\b",
        r"\b(?:chains?|chane)\b",
        r"\b(?:kadas?|kade|kara)\b",
        r"\b(?:necklaces?|haars?|har|harr|choker|mangalsutra|gal[ae]\s*k[aie]|gala|gale)\b",
        r"\b(?:earrings?|jhumk[ai]|balis?)\b",
        r"\b(?:anklets?|payal)\b",
        r"\b(?:pyrite|crystal)\b"
    ]
    GENDER_PATTERNS = r"\b(?:men|mens|male|mard|boys?|gents?|women|womens|female|aurat|girls?|ladies|mahila)\b"
    STYLE_PATTERNS = r"\b(?:gold|silver|diamond|rose\s*gold|ad|cz|pearl|mot[ie]|crystal|oxidised)\b"

    is_qualifier = any(bool(re.match(p, text_clean, re.IGNORECASE)) for p in QUALIFIER_PATTERNS)
    if is_qualifier and db and sender_phone:
        try:
            from models import ChatMessage
            clean_p = sender_phone.replace("+", "")
            recent_msgs = (
                db.query(ChatMessage)
                .filter(ChatMessage.customer_phone.in_([sender_phone, clean_p]))
                .order_by(ChatMessage.created_at.desc())
                .limit(8)
                .all()
            )
            # Scan backward through customer messages in this session to gather accumulated context
            accumulated_product = None
            accumulated_gender = None
            accumulated_style = None

            # First, check current message
            m_gen = re.search(GENDER_PATTERNS, text_clean, re.I)
            if m_gen: accumulated_gender = m_gen.group(0).lower()
            m_sty = re.search(STYLE_PATTERNS, text_clean, re.I)
            if m_sty: accumulated_style = m_sty.group(0).lower()

            for prev_m in recent_msgs:
                if prev_m.sender_type == "CUSTOMER" and prev_m.text:
                    p_txt = prev_m.text.strip().lower()
                    if not accumulated_product:
                        for pat in PRODUCT_TERMS:
                            m_p = re.search(pat, p_txt, re.I)
                            if m_p:
                                accumulated_product = m_p.group(0).lower()
                                break
                    if not accumulated_gender:
                        m_g = re.search(GENDER_PATTERNS, p_txt, re.I)
                        if m_g: accumulated_gender = m_g.group(0).lower()
                    if not accumulated_style:
                        m_s = re.search(STYLE_PATTERNS, p_txt, re.I)
                        if m_s: accumulated_style = m_s.group(0).lower()

            parts = [p for p in [accumulated_gender, accumulated_style, accumulated_product] if p]
            if parts and accumulated_product:
                text_clean = " ".join(parts)
                message_text = " ".join(parts)
                logger.info(f"[Bot Context Memory] Enriched multi-turn query: '{text_clean}'")
        except Exception as ctx_err:
            logger.warning(f"[Bot Context Memory] Failed to restore context: {ctx_err}")

    # -------------------------------------------------------------
    # 0. Check for Inbound Customer Image/Photo Message
    # If the customer sends a photo (e.g. of a ring, earring, or screenshot),
    # route to AI vision so the AI can inspect the design and find matching products.
    # -------------------------------------------------------------
    is_photo_message = bool(re.match(r"^\[IMAGE\]", text_clean, re.IGNORECASE) or text_clean == "[image]")
    if is_photo_message:
        message_text = "Customer shared this jewelry photo. Please inspect the design, identify the style/type, and recommend the best matching products from our store catalog."
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

        # Notify human support via email and pause AI so human team can monitor or take over if needed
        try:
            from services.email_notification_service import send_support_escalation_email
            from models import Contact
            clean_p = sender_phone.replace("+", "").strip()
            contact = db.query(Contact).filter(Contact.phone.in_([sender_phone, clean_p, f"+{clean_p}"])).first()
            if contact:
                attrs = dict(contact.custom_attributes or {})
                attrs["ai_disabled"] = True
                contact.custom_attributes = attrs
                db.commit()
            send_support_escalation_email(
                customer_phone=sender_phone,
                customer_name=customer_name,
                latest_message=message_text,
                order_info=text_reply
            )
        except Exception as e:
            logger.warning(f"[Bot Auto-Reply] Could not escalate order inquiry: {e}")

        return res

    # -------------------------------------------------------------
    # 2a. Support Request Escalation (e.g. "I need customer support", "It's in transit for 9 days")
    # We are sales, NOT support. Provide courteous acknowledgement, pause AI, and email support team!
    # -------------------------------------------------------------
    is_support_request = any(re.search(p, text_clean, re.I) for p in SUPPORT_ESCALATION_PATTERNS)
    if is_support_request:
        # Pause AI for this customer so bot stops sending sales pitches/products
        try:
            from models import Contact
            clean_p = sender_phone.replace("+", "").strip()
            contact = db.query(Contact).filter(Contact.phone.in_([sender_phone, clean_p, f"+{clean_p}"])).first()
            if contact:
                attrs = dict(contact.custom_attributes or {})
                attrs["ai_disabled"] = True
                contact.custom_attributes = attrs
                db.commit()
        except Exception as e:
            logger.warning(f"[Bot Auto-Reply] Error disabling AI for support escalation: {e}")

        # Send escalation email to ansbillion@gmail.com and jwlbillion@gmail.com
        try:
            from services.email_notification_service import send_support_escalation_email
            send_support_escalation_email(
                customer_phone=sender_phone,
                customer_name=customer_name,
                latest_message=message_text,
                chat_history=f"Customer Phone: {sender_phone}\nMessage: {message_text}"
            )
        except Exception as e:
            logger.warning(f"[Bot Auto-Reply] Error sending support escalation email: {e}")

        support_ack = (
            "Hello! Thank you for reaching out to JWL Billion. 🙏\n\n"
            "Your support request has been forwarded directly to our dedicated customer support team. "
            "Our representative is reviewing your details and will assist you shortly here on WhatsApp.\n\n"
            "Thank you for your patience!"
        )
        res = send_whatsapp_free_text(sender_phone, support_ack, db=db)
        _save_bot_message(db, sender_phone, support_ack, res.get("message_id"))
        return res

    # -------------------------------------------------------------
    # 2b. Cash on Delivery (COD) Priority Check
    # Ensures "Cash on delivery" queries NEVER get hijacked by order tracking
    # -------------------------------------------------------------
    is_cod_inquiry = any(re.search(p, text_clean, re.I) for p in COD_QUERY_PATTERNS)
    if is_cod_inquiry:
        cod_reply = (
            "Haan ji, 100% Cash on Delivery (COD) uplabdh hai pure India mein! 📦✨\n\n"
            "Parcel milne par hi aapko cash dena hai. Hamari official website par aap directly COD order place kar sakte hain:\n"
            "👉 https://jwlbillion.com\n\n"
            "Aapko kaun sa jewellery design sabse zyada pasand aaya?"
        )
        res = send_whatsapp_free_text(sender_phone, cod_reply, db=db)
        _save_bot_message(db, sender_phone, cod_reply, res.get("message_id"))
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
    # 4. Route Customer Messages to AI Assistant
    # All product inquiries, category requests, greetings, and conversational questions
    # are handled directly by Qwen AI with full Shopify catalog awareness, image sending,
    # and context-specific natural sales closing.
    # -------------------------------------------------------------
    try:
        from services.ai_assistant_service import generate_qwen_reply
        ai_result = generate_qwen_reply(message_text, sender_phone, db=db)
        if ai_result and ai_result.get("reply"):
            qwen_text = ai_result["reply"]
            image_to_send = ai_result.get("image_url")
            matched_prod = ai_result.get("product")

            # Check if this customer already received this exact image recently to prevent repeating photos
            if image_to_send and db and sender_phone:
                try:
                    from models import ChatMessage
                    clean_p = sender_phone.replace("+", "")
                    already_sent_photo = db.query(ChatMessage).filter(
                        ChatMessage.customer_phone.in_([sender_phone, clean_p]),
                        ChatMessage.sender_type != "CUSTOMER",
                        ChatMessage.media_url == image_to_send
                    ).first() is not None
                    if already_sent_photo:
                        image_to_send = None
                except Exception:
                    pass

            from services.link_tracking_service import rewrite_text_links, build_tracked_url
            from services.ai_assistant_service import _clean_product_photo
            qwen_text = rewrite_text_links(qwen_text, sender_phone, source="ai_chat")

            # Support sending multiple product images if AI recommended multiple designs (up to 3)
            # If customer specifically asked for designs/photos ("dikhao", "bhejo", "options", "photos", etc.),
            # ensure images are always dispatched even if previously viewed.
            explicit_design_request = bool(re.search(
                r"\b(?:design|designs|photo|photos|pic|pics|image|images|dikhao|dekhao|dekhna|bhejo|options|aur|dusra|chain|necklace|earring|ring|bracelet|kada|anklet)\b",
                text_clean, re.I
            ))

            products_to_send = ai_result.get("products") or ([matched_prod] if matched_prod else [])
            import time

            sent_images_count = 0
            for prod in products_to_send[:3]:
                prod_img = _clean_product_photo(prod)
                if not prod_img:
                    continue

                # Check if this customer already received this exact image in the last 60 seconds (prevents accidental double taps)
                if db and sender_phone and not explicit_design_request:
                    try:
                        from models import ChatMessage
                        from datetime import datetime, timedelta
                        clean_p = sender_phone.replace("+", "")
                        cutoff = datetime.utcnow() - timedelta(seconds=60)
                        already_sent = db.query(ChatMessage).filter(
                            ChatMessage.customer_phone.in_([sender_phone, clean_p]),
                            ChatMessage.sender_type != "CUSTOMER",
                            ChatMessage.media_url == prod_img,
                            ChatMessage.created_at >= cutoff
                        ).first() is not None
                        if already_sent:
                            continue
                    except Exception:
                        pass

                raw_prod_url = prod.get('product_url') or 'https://jwlbillion.com'
                tracked_prod_url = build_tracked_url(raw_prod_url, sender_phone, source="ai_chat")
                cap = (
                    f"*{prod.get('title')}*\n"
                    f"Link: {tracked_prod_url}"
                )
                media_res = send_whatsapp_media(sender_phone, "image", media_url=prod_img, caption=cap, db=db)
                _save_bot_message(
                    db,
                    sender_phone,
                    cap,
                    media_res.get("message_id"),
                    media_url=prod_img,
                    message_type="image"
                )
                sent_images_count += 1
                if sent_images_count < len(products_to_send[:3]):
                    time.sleep(0.5)

            res = send_whatsapp_free_text(sender_phone, qwen_text, db=db)
            _save_bot_message(db, sender_phone, qwen_text, res.get("message_id"))
            return res
    except Exception as qwen_err:
        logger.warning(f"[Bot Qwen Auto-Reply] Fallback triggered: {qwen_err}")

    # Fallback to category catalog matcher if AI produces no reply
    design_match_res = _match_and_send_product_designs(sender_phone, text_clean, db=db)
    if design_match_res:
        return design_match_res

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
    message_type: str = "text",
    channel: str = "general"
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
            channel=channel,
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
