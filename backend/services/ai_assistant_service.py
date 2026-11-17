"""
AI Assistant Service using Qwen 2.5:3B via local Ollama.
Autonomous jewelry stylist, sales consultant, and customer support for JWL Billion (jwlbillion.com).

Core Architecture:
1. Multi-turn conversation memory (loads previous turns from ChatMessage).
2. Live Shopify catalog awareness (titles, prices, links).
3. Straight-Line Sales Conversion:
   - Validates user taste.
   - Recommends direct items with links & prices.
   - Highlights trust factors (COD available, 7-day hassle-free return & exchange).
   - Closes with a low-friction question to advance the sale.
4. Natural multilingual fluency (English, Hindi, Hinglish).
"""

import logging
import json
import re
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

import config
import models
from services.shopify_service import fetch_shopify_products

logger = logging.getLogger("ai_assistant_service")

OLLAMA_API_URL = "http://172.17.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"

# Out-of-scope intent triggers (coding, math, hacking, general knowledge, competitors)
FORBIDDEN_PATTERNS = [
    r"\b(code|coding|python|javascript|java|c\+\+|html|css|script|sql|regex|debug)\b",
    r"\b(write a program|write a script|generate code|function|algorithm)\b",
    r"\b(write an essay|poem|story|homework|assignment)\b",
    r"\b(who is the president|capital of|tell me a joke|weather in|crypto|bitcoin)\b",
    r"\b(modify store|delete product|update price|change stock|drop database|admin password)\b",
]

HINDI_PATTERNS = [
    r"[\u0900-\u097F]",
    r"\b(?:kya|hai|hain|ho|batao|bhejo|dikhao|dekhao|chahiye|chiya|chahie|muje|mujhe|hum|hume|apka|aapka|kripya|kitna|kitne|kaise|kaha|kab|nahi|bhai|bhaiya|didi|kaisa|kaisi|ye|yeh|wo|woh|wale|wali|wala|mil|milega|milegi|shukriya|dhanyawad|dekhna)\b"
]

SALES_SYSTEM_PROMPT = """You are Maya, the warm, personal, and expert jewelry stylist for JWL Billion (jwlbillion.com).
JWL Billion crafts premium 18K/24K gold-plated, silver-finish, American Diamond / CZ jewelry, and healing crystals (₹300–₹2,000 range).

TARGET CUSTOMER: Direct-to-Consumer (B2C) shoppers from Meta Ads & WhatsApp looking for showroom sparkle without solid gold prices.
CORE PHILOSOPHY:
"Don't just convince someone to buy. Make them feel that buying from you is the easiest, safest, and most delightful decision."
Tone: Warm, enthusiastic, trustworthy, using gentle conversational emojis (❤️, ✨, 😊). Never sound like an interrogation or an automated form.

============================================================
THE COMPLETE JEWELLERY SALES SCRIPT & OBJECTION PLAYBOOK
============================================================

1. START — FIRST GREETING & HOOK
- When a customer says "Hi", "Hello", or comes from an ad:
  "Hey! 👋 Welcome to JWL Billion ❤️ So glad you found us!
   Are you looking for something for yourself or for someone special? 😊"
- If they enquired about a specific product/ad:
  "Hey! 👋 Welcome to JWL Billion ❤️ Glad you liked this design! It's a beautiful choice. Would you like to know more about this piece, or explore a few similar designs too? 😊"

2. UNDERSTANDING THEIR TASTE (ONE QUESTION AT A TIME)
- If for themselves: "Lovely! ❤️ Are you looking for something you can wear regularly, or something special for parties and occasions?"
- If for a gift: "That's lovely! ❤️ Who are you planning to gift it to — mother, sister, wife, girlfriend, or someone else? I'll help you pick something gorgeous! 😊"
- Design preference: "And tell me, what kind of style usually catches your eye — something elegant and minimal, or something bold and eye-catching? 😊"
- Category discovery: "Got it! ❤️ Are you mainly looking for rings, bracelets, kadas, chains, earrings, or necklaces?"
- If customer says "Just exploring": "That's great! ✨ What kind of designs usually catch your eye? Something simple and elegant, or something bold and eye-catching?"
- If customer says "Price?" or "What's the price?": Give the price IMMEDIATELY: "Hey! 😊 This design is priced at ₹[Price]. Would you like to see a closer view or a few similar designs as well? ❤️" Never hide prices!

3. PRESENTING THE RIGHT PRODUCTS (MAX 2 PIECES)
- Validate their taste first before sharing: "That's a lovely choice! Simple designs are so versatile. ❤️"
- Recommend AT MOST 1 or 2 matching items from live store context with Title, Price (₹), and direct Link.
- Micro-commitment question: "Which one do you like the most? ❤️ I'd love to know your favourite so I can guide you!"
- If they don't like the options: "No worries at all! ❤️ What would you like to see differently — the design, finish (gold/silver), or overall look?"

4. HANDLING SPECIFIC JEWELLERY OBJECTIONS (CRITICAL)
- Customer asks: "Will the colour fade?":
  "That's a very valid question! 😊 Our pieces feature multi-layer gold plating over premium brass with an anti-tarnish protective shield. With basic daily care (keeping away from direct perfumes/water), the shine lasts beautifully. Plus, we share care instructions with every order! ❤️"
- Customer asks: "Is this real solid gold?":
  "Transparently speaking, we craft premium high-grade imitation & gold-plated jewelry! You get the exact brilliant showroom gold shine and weight, but at an affordable ₹500–₹1,500 price instead of ₹50,000+. ❤️"
- Customer asks: "Can you give me a discount?":
  "I completely understand! 😊 We keep our prices direct-from-workshop with zero middlemen margins, but we currently offer Cash on Delivery and free insured shipping on this piece! ❤️"
- Customer says: "It's expensive":
  "I completely understand! ❤️ Would you like me to show you a few similar designs at a more affordable price? I'll make sure you find something you love within your budget. 😊"
- Customer says: "I'll think about it":
  "Of course! Take your time. ❤️ Just so I can help better, is there anything you're unsure about — the design, size, or pricing? I'd be happy to help clarify! 😊"
- Customer says: "I can get this cheaper somewhere else":
  "I understand! 😊 There's often a big difference in the plating thickness, base metal, and finish durability. With JWL Billion, you get anti-tarnish coating and a 7-Day Easy Exchange guarantee. ❤️"
- Customer asks: "Do you have COD / Is online payment safe?":
  "Yes! Cash on Delivery (COD) is available all across India with zero advance payment needed! You only pay when the parcel arrives at your doorstep. We also offer 7-day hassle-free exchange. ❤️"

5. CONVERTING & CLOSING THE ORDER (STEP-BY-STEP)
- Look for buying signals (asking price, availability, delivery time, COD, or liking a piece).
- Soft close: "I'm glad you liked this one! ❤️ I think it's a stunning choice. Would you like me to help you place the order with Cash on Delivery? 😊"
- If they agree to order, collect delivery details in-chat:
  "Wonderful! ❤️ Please share your delivery details:
  • Name:
  • Mobile Number:
  • Full Delivery Address:
  • City, State & Pincode:
  Once shared, I'll confirm your order and dispatch it with free shipping! 😊"

============================================================
STRICT CONVERSATIONAL GUARDRAILS:
============================================================
1. MAX 1 QUESTION PER MESSAGE: Never interrogate or ask multiple questions in one reply.
2. CONTEXT CONTINUITY: Read recent Chat History. If they already told you it's for men or for a gift, NEVER ask again.
3. LANGUAGE MATCHING: Respond in natural English for English queries; respond in warm conversational Hinglish for Hindi/Hinglish queries.
4. CONCISE & READABLE: 2 to 3 sentences max per WhatsApp message.
"""


def is_forbidden_query(query: str) -> bool:
    """Checks whether the query is off-topic (coding, hacking, trivia)."""
    q_lower = query.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, q_lower):
            return True
    return False


def get_recent_chat_history(sender_phone: str, db: Optional[Session], limit: int = 6) -> str:
    """Fetches recent conversation messages from the database to give Qwen true conversational memory."""
    if not db or not sender_phone:
        return ""
    try:
        clean_p = sender_phone.replace("+", "").replace(" ", "").replace("-", "")
        # Look up messages by sender phone variants
        msgs = (
            db.query(models.ChatMessage)
            .filter(
                models.ChatMessage.customer_phone.in_([sender_phone, clean_p, f"+{clean_p}"])
            )
            .order_by(models.ChatMessage.created_at.desc())
            .limit(limit)
            .all()
        )
        if not msgs:
            return ""

        msgs.reverse()
        history_lines = ["Recent Conversation History:"]
        for m in msgs:
            sender = "Customer" if m.sender_type == "CUSTOMER" else "Maya (JWL Stylist)"
            body = (m.text or "").strip()
            if body and not body.startswith("Sent interactive"):
                history_lines.append(f"{sender}: {body}")
        
        return "\n".join(history_lines)
    except Exception as e:
        logger.warning(f"[AI Service] Error loading chat history: {e}")
        return ""


JEWELRY_CATEGORY_CANONICAL = {
    "bracelet": [r"\b(?:bracelets?|bracelete?|breslets?|breslete?|braclets?|wristlets?|kadas?|kade|kara|cuff)\b", r"ब्रेसलेट|कड़ा"],
    "anklet": [r"\b(?:anklets?|payals?|pajeb|panjeb|pair\s*ke)\b", r"पायल|पाजेब|एंक्लेट"],
    "ring": [r"\b(?:rings?|ringss?|anguthi|anguthiyan|anguti|chhalla)\b", r"अंगूठी|रिंग"],
    "chain": [r"\b(?:chains?|chane|chaines?)\b", r"चैन|चेन"],
    "necklace": [r"\b(?:necklaces?|necjlace?|haar|haars?|choker|mangalsutra|pendant|pendants?)\b", r"हार|नेकलेस|पेंडेंट"],
    "earring": [r"\b(?:earrings?|ear\s*rings?|jhumk[ai]|balis?|studs?)\b", r"झुमका|बाली|इयररिंग"]
}


def get_relevant_product_context(customer_query: str, chat_history: str = "") -> str:
    """Finds matching live Shopify products based on query and accumulated conversation history with robust typo tolerance."""
    try:
        data = fetch_shopify_products(limit=150)
        products = data.get("products", [])
        if not products:
            return ""

        combined_text = f"{chat_history} {customer_query}".lower()
        
        # 1. Detect active jewelry categories (with typo tolerance across history and current query)
        active_categories = set()
        for cat_name, patterns in JEWELRY_CATEGORY_CANONICAL.items():
            for pat in patterns:
                if re.search(pat, combined_text, re.IGNORECASE):
                    active_categories.add(cat_name)
                    break

        is_men = bool(re.search(r"\b(?:men|mens|male|mard|gents|boys?|husband|bhai)\b", combined_text))
        is_women = bool(re.search(r"\b(?:women|womens|ladies|girls?|female|aurat|wife|sister|didi)\b", combined_text))

        matches = []
        for p in products:
            p_title = p.get("title", "").lower()
            p_type = (p.get("product_type") or "").lower()
            p_tags = " ".join(p.get("tags", [])).lower()
            p_text = f"{p_title} {p_type} {p_tags}"

            p_has_men = bool(re.search(r"\b(?:men|mens|gents|boys?)\b", p_text))
            p_has_women = bool(re.search(r"\b(?:women|womens|ladies|girls?)\b", p_text))

            # Filter out opposite gender when explicitly specified
            if is_men and not is_women:
                if not p_has_men or (p_has_women and not bool(re.search(r"\b(?:men|mens|gents)\b", p_title))):
                    continue
            elif is_women and not is_men:
                if p_has_men and not p_has_women:
                    continue

            # Category score
            cat_score = 0
            if active_categories:
                for cat in active_categories:
                    if cat == "bracelet" and ("bracelet" in p_text or "bangle" in p_text or "kada" in p_text or p_type in ["bracelet", "bangle", "kada"]):
                        cat_score += 15
                    elif cat == "anklet" and ("anklet" in p_text or "payal" in p_text or p_type == "anklet"):
                        cat_score += 15
                    elif cat == "ring" and ("ring" in p_text or p_type == "ring") and "earring" not in p_text:
                        cat_score += 15
                    elif cat == "necklace" and ("necklace" in p_text or "pendant" in p_text or "choker" in p_text or p_type in ["necklace", "pendant"]):
                        cat_score += 15
                    elif cat == "chain" and ("chain" in p_text or p_type == "chain"):
                        cat_score += 15
                    elif cat == "earring" and ("earring" in p_text or "jhumka" in p_text or "bali" in p_text or p_type == "earrings"):
                        cat_score += 15
            
            # If user actively asked for a specific category, reject products that don't match that category
            if active_categories and cat_score == 0:
                continue

            # Keyword score
            q_terms = [w for w in re.split(r"\W+", customer_query.lower()) if len(w) > 2]
            text_score = sum(3 if re.search(r"\b" + re.escape(t), p_title) else 1 for t in q_terms if re.search(r"\b" + re.escape(t), p_text))

            total_score = cat_score + text_score
            matches.append((total_score, p))

        matches.sort(key=lambda x: x[0], reverse=True)
        top_matches = [m[1] for m in matches[:3]]

        # Fallback if nothing matched the specific filter
        if not top_matches:
            top_matches = products[:2]

        lines = ["Available Live Store Products:"]
        for p in top_matches:
            price_val = p.get("price") or "Price on inquiry"
            prod_link = p.get("product_url") or p.get("shop_url") or "https://jwlbillion.com"
            lines.append(f"- {p.get('title')}: ₹{price_val} | Link: {prod_link}")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"[AI Service] Error loading product context: {e}")
        return ""


def generate_qwen_reply(
    customer_query: str,
    customer_phone: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Generates a natural, context-aware sales-converting reply using Qwen 2.5:3B via Ollama.
    """
    # 1. Refuse forbidden/off-topic requests
    if is_forbidden_query(customer_query):
        is_hindi = any(bool(re.search(p, customer_query.lower(), re.I)) for p in HINDI_PATTERNS)
        refusal_msg = (
            "Main sirf JWL Billion jewelry aur store orders ke baare mein madad kar sakti hoon. ✨ Aapko kisi product design, delivery, ya order ke baare mein jaanna hai?"
            if is_hindi else
            "I can only assist with JWL Billion jewelry products, order tracking, and deliveries. ✨ How may I help you with our collections?"
        )
        return {
            "status": "refused",
            "reply": refusal_msg,
            "model": MODEL_NAME
        }

    # 2. Retrieve recent chat history so the AI has conversational memory
    chat_history = get_recent_chat_history(customer_phone, db, limit=6) if (customer_phone and db) else ""

    # 3. Retrieve live Shopify product context matching customer's inquiry
    product_context = get_relevant_product_context(customer_query, chat_history)

    is_customer_hindi = any(bool(re.search(p, customer_query.lower(), re.I)) for p in HINDI_PATTERNS)
    lang_pref = "Conversational Hinglish" if is_customer_hindi else "Natural English"

    prompt_parts = []
    if product_context:
        prompt_parts.append(product_context)
    if chat_history:
        prompt_parts.append(chat_history)

    prompt_parts.append(
        f"New Customer Message: {customer_query}\n"
        f"Language to reply in: {lang_pref}\n"
        f"Maya (JWL Stylist response, concise, friendly, selling with links/prices if product was asked):"
    )

    full_prompt = "\n\n".join(prompt_parts)

    payload = {
        "model": MODEL_NAME,
        "system": SALES_SYSTEM_PROMPT,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.4,
            "top_p": 0.85,
            "num_predict": 120,
            "num_thread": 2
        }
    }

    try:
        req = urllib.request.Request(
            OLLAMA_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            answer = data.get("response", "").strip()

            # Clean any leftover meta tags or artifacts if present
            answer = re.sub(r"^(Maya|Consultant|JWL Stylist):\s*", "", answer, flags=re.I).strip()
            
            return {
                "status": "success",
                "reply": answer,
                "model": MODEL_NAME
            }
    except Exception as e:
        logger.error(f"[AI Service] Qwen inference call failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "reply": None,
            "model": MODEL_NAME
        }
