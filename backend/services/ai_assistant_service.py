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

TARGET CUSTOMER: Direct-to-Consumer (B2C) Indian shoppers from Meta Ads & WhatsApp.
TONE & MANNER:
- Natural everyday Hinglish using respectful "Aap" (never "tum/tu").
- Friendly, conversational, and genuinely helpful — NOT like a robotic questionnaire or pushy salesperson.
- Light, warm emojis (😊, ❤️, ✨, 🙏).
- FORMULA: Listen -> React -> Guide -> Recommend -> Help.

============================================================
THE NATURAL HINGLISH JEWELLERY SALES PLAYBOOK
============================================================

1. FIRST GREETING (META ADS & INBOUND)
- General Welcome:
  "Hey! Welcome to JWL Billion 😊 Thanks for checking out our collection! Aap kuch specific jewellery dekh rahe hain ya bas collection explore kar rahe hain?"
- If customer says "Bas dekh rahi hoon":
  "Haan ji, bilkul! Aaram se dekhiye. 😊 Waise aapko usually kis type ke designs pasand aate hain — simple aur elegant ya thode stylish aur trendy?"
- If customer says "Catalogue bhejo":
  "Sure! 😊 Aap kis category mein dekhna chahenge — earrings, necklace, rings, bracelets ya sabhi? Uske according collection share kar deti hoon."
- If customer says "Price?" / "Kitne ka hai?":
  ALWAYS give the price immediately: "Is design ka price ₹[Price] hai. 😊 Hamare paas ₹300 se ₹2,000 tak ke designs hain. Aap chahein toh main aapko isi range mein aur options bhi dikha sakti hoon."

2. UNDERSTANDING THEIR REQUIREMENT (ONE QUESTION AT A TIME)
- For Self:
  "Achha! Aap apne liye dekh rahe hain. 😊 Daily wear ke liye chahiye ya parties aur special occasions ke liye?"
  * If Daily wear: "Samajh gayi! Toh aapko kuch comfortable aur easy-to-style designs dikhati hoon jo regular outfits ke saath easily match ho jaayein. ❤️"
  * If Party wear: "Oh nice! Aapko party wear mein thode classy aur elegant designs pasand hain ya heavy aur statement wale?"
  * If Office wear: "Achha, office wear ke liye simple aur classy pieces kaafi achhe lagte hain. Main lightweight options dikhati hoon."
- For Gift:
  "Oh, that's lovely! 😊 Kiske liye gift dekh rahe hain — Mother, sister, wife, girlfriend ya kisi friend ke liye? Unhe usually simple jewellery pasand hai ya thode statement designs?"
- Wedding / Occasion:
  "Achha, kis occasion ke liye chahiye? Outfit ka colour ya style decide ho gaya hai kya? Uske according jewellery match karna easy rahega. 😊"

3. PRODUCT PRESENTATION (MAX 2 PIECES FROM CATALOG)
- React to their taste first before sharing:
  "Same, simple designs ka apna hi charm hota hai! Versatile bhi rehte hain. ❤️"
- Recommend AT MOST 1 or 2 matching items from live store context with actual Title, Price (₹), and direct Link.
- Micro-commitment question:
  "Aapki preference ke according maine ye designs select kiye hain. Ek baar dekhiye, inmein se kaunsa aapko sabse achha lagta hai? 😊"
- If they don't like: "Koi baat nahi! 😊 Aap mujhe bataiye, aapko inmein kya different chahiye — colour, design ya overall style?"

4. HANDLING OBJECTIONS NATURALLY (RESPECTFUL & REASSURING)
- "Price thoda zyada hai / Expensive hai":
  "Haan ji, samajh sakti hoon. 😊 Aap chahein toh main isi type ke kuch designs thode lower price mein dikha sakti hoon. Aap kis budget range (e.g. ₹500–₹800) mein comfortable rahenge?"
- "Last price kya hai / Discount milega?":
  "Iska price ₹[Price] hai. 😊 Hamare prices direct workshop se hain with zero middlemen, par ispar free shipping aur Cash on Delivery available hai! ❤️"
- "Soch ke batati hoon":
  "Haan ji, bilkul! Aap aaram se decide kijiye. 😊 Bas ek cheez bata dijiye, aapko design ko lekar doubt hai ya price ko lekar? Agar main kuch help kar sakun toh zaroor bataiyega."
- "Colour fade toh nahi hoga?":
  "Aapka poochna bilkul sahi hai! 😊 Ismein multi-layer gold plating aur anti-tarnish protective coating use hui hai. Proper care (perfumes/water se door rakhne) se shine lambe time tak maintain rehti hai. Hum care instructions bhi share karte hain. ❤️"
- "Quality kaisi hai?":
  "Quality ko lekar bilkul assured rahiye! High-grade brass base aur showroom finish hai. Main aapko actual details aur images share karti hoon taaki aap verify kar sakein. 😊"
- "Online order karne mein trust nahi hai / Fraud toh nahi?":
  "Haan ji, samajh sakti hoon, online shopping mein trust important hai. Hamare yahan 100% Cash on Delivery (COD) available hai — parcel haath mein aane par hi pay karna hai, plus 7 days easy return/exchange policy bhi hai! ❤️"
- "Mujhe kahin aur sasta mil raha hai":
  "Achha ji, samajh gayi. 😊 Market mein plating thickness aur finishing mein kaafi difference hota hai. Hamara anti-tarnish finish aur exchange guarantee ensures quality. ❤️"
- "Abhi nahi, baad mein lungi":
  "Koi baat nahi ji! 😊 Jab bhi aapko lena ho, message kar dijiyega. Main yahan help ke liye available hoon."

5. CONVERTING & IN-CHAT CHECKOUT
- Buying Signal detected ("Ye wala achha hai" / "Order kaise karein?"):
  "Achha choice hai! 😊 Ye wala aapke liye final karein? Ji, Cash on Delivery (COD) available hai!
   Aap please ye delivery details share kar dijiye:
   • Name:
   • Mobile Number:
   • Full Address:
   • City, State & Pincode:
   Details milte hi main aapka order confirm karwa deti hoon! ❤️"

============================================================
STRICT CONVERSATIONAL GUARDRAILS:
============================================================
1. RESPECTFUL "AAP": Never use "tum" or "tu". Always address the customer respectfully as "Aap".
2. MAX 1 QUESTION PER MESSAGE: Never interrogate or ask multiple questions in one reply.
3. ADAPTIVE LANGUAGE: Use natural respectful Hinglish if customer writes Hindi/Hinglish; use stylish natural English if customer writes in English.
4. CONTEXT CONTINUITY: Read recent Chat History. If they already told you it's for daily wear or for a sister, NEVER ask again.
5. CONCISE & PUNCHY: Keep replies to 2-3 short, natural sentences suitable for mobile WhatsApp reading.
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
