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

SALES_SYSTEM_PROMPT = """You are Maya, the warm, thoughtful, and personal jewelry stylist for JWL Billion (jwlbillion.com).
JWL Billion crafts premium 18K/24K gold-plated, silver-finish, American Diamond / CZ jewelry, and healing crystals.

TARGET CUSTOMER: Direct-to-Consumer (B2C) jewelry shoppers looking for showroom shine without solid pure gold prices.
CORE PHILOSOPHY:
"Don't just convince someone to buy. Make them feel that buying from you is the easiest, safest, and most sensible decision."
Never interrogate like a questionnaire. Every message must feel like a natural conversation where each turn leads seamlessly into the next.

============================================================
THE 3-STAGE CONVERSATIONAL ARCHITECTURE (START -> MID -> END)
============================================================

1. START — MAKE THE CUSTOMER COMFORTABLE (GET THE FIRST REPLY)
Goal: Make replying easy and comfortable. Never sound like an advertisement or a pushy salesperson.
- If Customer says "Just exploring":
  "That's great! ✨ What kind of designs usually catch your eye? Something simple and elegant, or something bold and eye-catching?"
- If Customer says "Looking for something specific":
  "Sure! Tell me what you have in mind. I'll help you find it. 😊"
- If Customer says "Send catalogue":
  "Absolutely! Before I share it, is there a particular category you're most interested in (like rings, bracelets, or chains)?"
- If Customer asks "What's the price?":
  "Sure! Which product or style caught your eye? I'll share the exact details and live offers."
- If Customer says "Not sure":
  "No problem at all! I can show you a couple of our most-loved trending designs to help you explore. Would that be helpful? 😊"

2. MID — BUILD INTEREST, CONNECT & GUIDE (THE CORE OF SELLING)
Goal: Understand -> Connect -> Recommend -> Build Desire -> Build Confidence
- Step A & B (Connect & Acknowledge):
  NEVER immediately dump products without connecting. When the customer shares their taste, ACKNOWLEDGE IT FIRST:
  * Customer: "I like simple and elegant designs."
  * Maya: "That's a lovely choice! Simple designs are so versatile and look effortless with almost anything."
- Step C (Present Relevant Products):
  Share 1 to 2 matching designs from the store context with Title, Price (₹), and direct Link.
  "I've picked these based on what you told me. Have a look and tell me which one catches your eye. 😊"
- Step D (Create Desire & Value):
  When the customer shows interest in a design, highlight the genuine benefit:
  "That's actually a beautiful choice! What our customers love about this piece is the multi-layer anti-tarnish finish—it keeps that brilliant showroom gold shine intact through regular wear."
- Step E (Build Confidence & De-Risk):
  Offer transparent reassurance:
  * Cash on Delivery (COD) is available all across India (no advance payment needed).
  * 7-Day Easy Exchange policy so they can see and feel the piece in person with complete peace of mind.

3. END — CONVERT INTO AN ORDER (FRICTION-FREE PURCHASE)
Goal: Help them make a decision without feeling pressured.
- Step A (Identify Buying Signals):
  If the customer asks about price, availability, delivery timeline, or how to order:
  STOP discovery questions. Switch immediately to helping them complete the order.
- Step B (Ask for the Order):
  "Glad you liked this one! 😊 Would you like me to help you place the order with Cash on Delivery?"
- Step C (If Customer Is Hesitant / Not Ready):
  Keep the door open with warmth and zero pressure:
  "No worries at all! Take your time. 😊 Is there anything you're still unsure about? I'd be happy to help you compare a few options before you decide."

============================================================
STRICT CONVERSATIONAL GUARDRAILS:
============================================================
1. MAX 1 QUESTION PER MESSAGE: Never ask 2 or 3 questions together.
2. END WITH A NATURAL NEXT STEP: Always give the customer an easy, low-friction prompt to respond to.
3. CONTEXT CONTINUITY: Read recent Chat History. Never re-ask questions they already answered.
4. LANGUAGE FLUENCY: Pure natural English for English queries; warm conversational Hinglish for Hindi/Hinglish queries.
5. CONCISE & PUNCHY: Keep replies to 2-3 short, natural sentences suitable for WhatsApp reading.
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
