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
    r"\b(?:kya|keya|kia|h|hai|hain|he|ho|batao|bhejo|dikhao|dekhao|chahiye|chiya|chahie|muje|mujhe|hum|hume|apka|aapka|kripya|kitna|kitne|kaise|kaha|kab|nahi|bhai|bhaiya|didi|kaisa|kaisi|ye|yeh|wo|woh|wale|wali|wala|mil|milega|milegi|shukriya|dhanyawad|dekhna|soch|ke|batati|batata|achha|acha|sahi|bilkul|aur|kuch|kisko|kiske|apne|liye)\b"
]

SALES_SYSTEM_PROMPT = """You are Maya, warm, personal jewelry stylist for JWL Billion (jwlbillion.com).
JWL Billion crafts premium 18K/24K gold-plated, silver-finish, American Diamond / CZ jewelry (₹300–₹2,000).

CORE CONVERSATION RULES:
1. STRICT NATURAL HINGLISH WITH RESPECTFUL "AAP":
   - Speak ONLY in natural, fluent Romanized Hinglish (Hindi written in English alphabet, e.g. "Haan ji, iska price ₹749 hai. Aapko simple design dekhna hai ya thoda trendy?").
   - NEVER write broken grammar like 'likha', 'karenga', or 'dekhna pasand karenga'. Always write grammatically correct Hindi: "Aap dekhna chahenge?", "Aapko kaisa design pasand hai?".
   - NEVER write in pure English sentences. NEVER write in Devanagari script.
   - Always use respectful "Aap" (never use tu/tum).
2. NEVER DUMP MULTIPLE PRODUCT TITLES:
   - Pick at most 1 featured matching product. Share its title, price, and full link.
   - Do NOT construct awkward multi-option questions like 'Aapko X dekhna hai ya Y dekhna hai ya Z dekhna hai?'.
3. FORMULA: Listen -> React -> Recommend 1 Item with Link -> Ask 1 simple styling question.
4. PRICE DISCLOSURE: If asked "Price?", give the exact ₹ price immediately! Never hide it.
5. RECOMMENDATION & LINK RULES (CRITICAL):
   - When recommending or sharing a product, output the FULL product URL starting with https:// directly in the text!
   - NEVER EVER say '[Link]', '[here]', or use markdown link syntax like [text](url).
   - WhatsApp does NOT support markdown links. Write the complete link directly so customer can click it.

Keep replies to 2 short sentences in Roman Hinglish. End with a friendly question or clear next step."""


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
    "chain": [r"\b(?:chains?|chane|chaines?|chen|chene|cene)\b", r"चैन|चेन"],
    "necklace": [r"\b(?:necklaces?|necjlace?|haar|haars?|choker|mangalsutra|pendant|pendants?)\b", r"हार|नेकलेस|पेंडेंट"],
    "earring": [r"\b(?:earrings?|ear\s*rings?|jhumk[ai]|balis?|studs?)\b", r"झुमका|बाली|इयररिंग"]
}


def get_relevant_product_context(customer_query: str, chat_history: str = "") -> tuple[str, list[dict]]:
    """Finds matching live Shopify products based on query and accumulated conversation history with robust typo tolerance."""
    try:
        data = fetch_shopify_products(limit=150)
        products = data.get("products", [])
        if not products:
            return "", []

        combined_text = f"{chat_history} {customer_query}".lower()
        
        # 1. Detect active jewelry categories (with typo tolerance across history and current query)
        active_categories = set()
        for cat_name, patterns in JEWELRY_CATEGORY_CANONICAL.items():
            for pat in patterns:
                if re.search(pat, combined_text, re.IGNORECASE):
                    active_categories.add(cat_name)
                    break

        is_men = bool(re.search(r"\b(?:men|mens|male|mard|gents|boys?|husband|bhai)\b", combined_text))
        is_women = bool(re.search(r"\b(?:women|womens|ladies|ledis|ladis|ledies|girls?|female|aurat|wife|sister|didi)\b", combined_text))

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
        # Limit to 1 primary top match in prompt context to prevent LLM listing multiple products in broken sentences
        top_matches = [m[1] for m in matches[:1]]

        # Fallback if nothing matched the specific filter
        if not top_matches:
            top_matches = products[:1]

        lines = ["Available Live Store Products:"]
        for p in top_matches:
            price_val = p.get("price") or "Price on inquiry"
            prod_link = p.get("product_url") or p.get("shop_url") or "https://jwlbillion.com"
            lines.append(f"- {p.get('title')}: ₹{price_val} | Product Link: {prod_link}")
        return "\n".join(lines), top_matches
    except Exception as e:
        logger.warning(f"[AI Service] Error loading product context: {e}")
        return "", []


def generate_qwen_reply(
    customer_query: str,
    customer_phone: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Generates a natural, context-aware sales-converting reply using Qwen 2.5 via Ollama.
    """
    q_clean = (customer_query or "").strip().lower()

    # 0a. Instant Fast-Path for Meta Ads Default Inbound ("Hello! Can I get more info on this?")
    if re.search(r"^(?:hello!?\s*)?can\s*i\s*get\s*more\s*info\s*(?:on\s*this)?\??$", q_clean):
        welcome_hinglish = (
            "Hey! Welcome to JWL Billion 😊\n\n"
            "Thanks for checking out our collection!\n\n"
            "Aap kuch specific jewellery dekh rahe hain ya bas collection explore kar rahe hain?"
        )
        return {"status": "success", "reply": welcome_hinglish, "model": "qwen2.5:1.5b"}

    # 0b. Instant Fast-Path for How are you / Kaise ho
    if re.search(r"\b(?:kaise\s*ho|kaisa\s*hai|kaisi\s*ho|kya\s*haal|kem\s*cho|how\s*are\s*you)\b", q_clean):
        kaise_reply = "Main badhiya hoon, aap bataiye aap kaise hain! 😊 JWL Billion mein aapka swagat hai. Aaj aapke liye kya collection dekhna chahenge?"
        return {"status": "success", "reply": kaise_reply, "model": "playbook"}

    # 0c. Instant Fast-Path for Common Exploring / Greeting Hooks (0.01s latency)
    if re.search(r"^(?:lets?\s*explore|just\s*(?:exploring|looking|browsing)|bas\s*dekh\s*(?:rahi|raha)\s*hoon)$", q_clean):
        is_hindi = bool(re.search(r"[\u0900-\u097F]|(?:bas|dekh|rahi|raha|hoon)", q_clean))
        if is_hindi:
            fast_reply = "Haan ji, bilkul! Aaram se dekhiye. 😊 Waise aapko usually kis type ke designs pasand aate hain — simple aur elegant ya thode stylish aur trendy?"
        else:
            fast_reply = "That's great! ✨ What kind of designs usually catch your eye — something simple and elegant, or something bold and eye-catching?"
        return {"status": "success", "reply": fast_reply, "model": "qwen2.5:1.5b"}

    # 0c. Objections & Natural Playbook Fast-Paths (Accurate, Instant & Hinglish)
    if re.search(r"\b(?:fade|color\s*fade|colour\s*fade|kaala|kala|rang\s*(?:nikal|uth|fade)|tarnish)\b", q_clean):
        fade_reply = "Ismein anti-tarnish coating ke sath multi-layer gold plating hai. ❤️ Normal water aur perfume se bacha kar rakhein toh shine lambe time tak maintain rehti hai. Saath mein care guide bhi milti hai!"
        return {"status": "success", "reply": fade_reply, "model": "playbook"}

    if re.search(r"\b(?:trust|bharosa|fraud|scam|online\s*order|fake)\b", q_clean):
        trust_reply = "Aapka doubt bilkul sahi hai! 😊 JWL Billion par 100% Cash on Delivery (COD) available hai — parcel haath mein milne ke baad hi pay karna hai, plus 7-day easy exchange bhi hai."
        return {"status": "success", "reply": trust_reply, "model": "playbook"}

    if re.search(r"\b(?:cod|cash\s*on\s*delivery)\b", q_clean):
        cod_reply = "Haan ji, 100% Cash on Delivery (COD) uplabdh hai pure India mein! Parcel milne par hi cash dena hai. 😊 Aapko kaun sa design pasand aaya?"
        return {"status": "success", "reply": cod_reply, "model": "playbook"}

    if re.search(r"\b(?:expensive|mehnga|mahnga|thoda\s*kam|discount|offer|last\s*price|kam\s*karo)\b", q_clean):
        disc_reply = "Haan ji, samajh sakti hoon! 😊 Hamare paas ₹300 se lekar ₹2,000 tak har range mein sundar designs hain. Aap kis budget range (jaise ₹500–₹800) mein dekhna chahenge?"
        return {"status": "success", "reply": disc_reply, "model": "playbook"}

    if re.search(r"\b(?:soch\s*ke|baad\s*mein|dekh\s*kar\s*batat|later)\b", q_clean):
        soch_reply = "Haan ji, bilkul! Aap araam se decide kijiye. 😊 Bas ek baat batayein, aapko design pasand aaya ya price ko lekar koi doubt hai?"
        return {"status": "success", "reply": soch_reply, "model": "playbook"}

    if re.search(r"\b(?:daily\s*wear|office|regular|daily)\b", q_clean):
        daily_reply = "Samajh gayi! Daily & office wear ke liye simple, lightweight aur classy pieces sabse best rehte hain. Main aapko kuch comfortable options share karti hoon. 😊"
        return {"status": "success", "reply": daily_reply, "model": "playbook"}

    if re.search(r"\b(?:party|wedding|shaadi|function|heavy|occasion)\b", q_clean):
        party_reply = "Oh nice! Special occasions ke liye statement aur elegant designs kaafi suit karte hain. Aapko matching necklace set dekhna hai ya bracelet/earrings?"
        return {"status": "success", "reply": party_reply, "model": "playbook"}

    if re.search(r"\b(?:gift|gifting|kisi\s*ko\s*dena)\b", q_clean):
        gift_reply = "That's lovely! 😊 Kiske liye gift dekh rahe hain — sister, wife, mother ya kisi friend ke liye? Main unke taste ke according best options suggest kar dungi."
        return {"status": "success", "reply": gift_reply, "model": "playbook"}

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
    product_context, top_matches = get_relevant_product_context(customer_query, chat_history)

    # Default to Conversational Hinglish for all Indian customer conversations,
    # unless customer explicitly asks or speaks in pure formal English without Indian phrasing
    combined_convo = f"{chat_history} {customer_query}".lower()
    is_pure_english = bool(re.search(r"^[a-zA-Z0-9\s\.,!\?']+$", customer_query)) and not any(bool(re.search(p, combined_convo, re.I)) for p in HINDI_PATTERNS)
    # Even if in English, if it's an initial Meta inquiry or greeting, we greet in warm Hinglish
    lang_pref = "Conversational Hinglish"

    prompt_parts = []
    if product_context:
        prompt_parts.append(product_context)
    if chat_history:
        prompt_parts.append(chat_history)

    prompt_parts.append(
        f"New Customer Message: {customer_query}\n"
        f"Language to reply in: {lang_pref}\n"
        f"CRITICAL INSTRUCTION: Reply in warm, natural Hindi / Hinglish with respectful 'Aap'. Be precise, helpful, and concise (2 short sentences).\n"
        f"Maya (JWL Stylist response, concise, friendly, selling with links/prices if product was asked):"
    )

    full_prompt = "\n\n".join(prompt_parts)

    payload = {
        "model": "qwen2.5:1.5b",
        "system": SALES_SYSTEM_PROMPT,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.85,
            "num_predict": 70,
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
            
            # Clean markdown link syntax: WhatsApp does not support markdown links like [here](https://...)
            # Convert [text](url) -> url so WhatsApp displays a clean, clickable preview link
            answer = re.sub(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)', r'\2', answer)
            # Also clean broken markdown patterns like [Product Link](https://...) or [text]\s*\((https?://...)\)
            answer = re.sub(r'\[[^\]]*\]\s*\(?(https?://[^\s\)]+)\)?', r'\1', answer)

            # If Qwen outputted literal placeholder like [Link], [here], [view] instead of the actual URL
            if top_matches and re.search(r'\[(?:Link|here|view|details?|product|website|Product Link)\]', answer, re.I):
                primary_url = top_matches[0].get("product_url") or top_matches[0].get("shop_url") or "https://jwlbillion.com"
                answer = re.sub(r'\[(?:Link|here|view|details?|product|website|Product Link)\]', primary_url, answer, flags=re.I)

            # Prevent weird halucinated repetitive names or phrases like "Keya, " at the start
            answer = re.sub(r'^(?:Keya|Kya),?\s*', '', answer, flags=re.I).strip()

            # Clean broken Hindi grammar patterns generated by small LLMs
            answer = re.sub(r'\blikha\s+chahiye\b', 'dekhna chahenge', answer, flags=re.I)
            answer = re.sub(r'\blikha\b', 'dekhna', answer, flags=re.I)
            answer = re.sub(r'\bkarenga\b', 'karenge', answer, flags=re.I)
            answer = re.sub(r'\bdekhna\s+pasand\s+kareng[ae]\b', 'dekhna chahenge', answer, flags=re.I)
            answer = re.sub(r'\bpasand\s+karenga\b', 'pasand karenge', answer, flags=re.I)
            answer = re.sub(r'\bchahe\?', 'chahenge?', answer, flags=re.I)
            
            return {
                "status": "success",
                "reply": answer,
                "model": "qwen2.5:1.5b"
            }
    except Exception as e:
        logger.error(f"[AI Service] Qwen inference call failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "reply": None,
            "model": MODEL_NAME
        }
