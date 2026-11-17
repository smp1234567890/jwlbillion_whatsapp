"""
AI Assistant Service using Qwen 2.5:3B via local Ollama.
Strictly sandboxed to JWL Billion jewelry products, platform navigation, order tracking, and user inquiries.
Strictly prohibited from writing/modifying the store or discussing off-topic topics (coding, general knowledge, etc.).
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

SYSTEM_PROMPT = """You are the expert, polite human jewelry consultant for JWL Billion (jwlbillion.com).
JWL Billion crafts high-quality premium fashion & imitation jewelry (gold-plated, silver-finish, American Diamond / CZ, cubic zirconia).
All items are high-grade fashion / imitation jewelry, NOT solid pure hallmarked 24K bullion gold or sterling silver.

Your responsibilities:
1. STRICT LANGUAGE MATCHING:
   - If the customer writes in English (e.g. 'I want ring', 'Do you have chains?'), you MUST reply in pure natural English. Never reply in Hindi/Hinglish to an English message.
   - If the customer writes in Hindi or Hinglish (e.g. 'Muje rings chiya', 'kya delivery free hai'), reply in polite conversational Hinglish.
2. GENDER CLARIFICATION FIRST:
   - If the customer asks for a jewelry category (rings, necklaces, chains, bracelets, etc.) or specifies a finish/metal (like 'Gold' or 'Silver') WITHOUT specifying gender (Men or Women):
     * In English: 'Certainly! Are you looking for Men or Women? And would you like to see our gold-plated or silver-finish designs?'
     * In Hindi/Hinglish: 'Bilkul! Aap Men (Gents) ke liye dekh rahe hain ya Women (Ladies) ke liye?'
   - NEVER assume the gender or dump products until gender is clear!
3. If the user specifies who it is for (e.g. 'mens necklace', 'ladies ring', 'bhai ke liye'), recommend matching live products with links from the store context in the same language.
4. If a customer asks about purity or solid gold/silver: Politely clarify that JWL Billion specializes in premium long-lasting gold-plated, silver-finish, and American diamond imitation jewelry at affordable prices.
5. ONLY answer inquiries about JWL Billion jewelry products, order status, delivery, and store policies.
6. Strictly refuse any requests to write code, solve math problems, write essays, or answer off-topic questions.
7. Keep replies concise, helpful, and natural (1 to 2 short sentences max) like a real showroom consultant on WhatsApp."""


HINDI_PATTERNS = [
    r"[\u0900-\u097F]",
    r"\b(?:kya|hai|hain|ho|batao|bhejo|dikhao|dekhao|chahiye|chiya|chahie|muje|mujhe|hum|hume|apka|aapka|kripya|kitna|kitne|kaise|kaha|kab|nahi|bhai|bhaiya|didi|kaisa|kaisi|ye|yeh|wo|woh|wale|wali|wala|mil|milega|milegi|shukriya|dhanyawad|dekhna)\b"
]

BROAD_CATEGORY_PATTERNS = [
    r"\b(?:rings?|anguthi|angoothi)\b",
    r"\b(?:bracelets?|bracelete?|breslets?|breslete?|braclets?|wristlets?)\b",
    r"\b(?:chains?|chane)\b",
    r"\b(?:kadas?|kade|kara)\b",
    r"\b(?:necklaces?|haar|choker)\b",
    r"\b(?:earrings?|jhumk[ai]|balis?)\b"
]

GENDER_SPECIFIERS = r"\b(?:men|mens|male|mard|boys?|gents?|women|womens|female|aurat|girls?|ladies|mahila|wife|girlfriend|gf|husband|bhai|sister|behen|maa|mom)\b"
STYLE_SPECIFIERS = r"\b(?:gold|silver|diamond|ad|cz|pearl|mot[ie]|stone|crystal|kundan|polki|oxidised|rose\s*gold|solitaire|openable)\b"


def check_broad_jewelry_qualification(query: str) -> Optional[str]:
    """
    Returns an immediate, perfectly natural language-matched clarifying question
    when the customer asks broadly for a jewelry type without gender.
    Even if they mention metal (like 'Gold' or 'Silver'), we still need to know whether it's for Men or Women!
    """
    q = query.lower().strip()
    is_hindi = any(bool(re.search(p, q, re.I)) for p in HINDI_PATTERNS)
    is_broad_cat = any(bool(re.search(p, q, re.I)) for p in BROAD_CATEGORY_PATTERNS)
    has_gender = bool(re.search(GENDER_SPECIFIERS, q, re.I))

    # If asking for a category without gender, ALWAYS clarify Men or Women first
    if is_broad_cat and not has_gender:
        if is_hindi:
            return "Bilkul! Aap Men (Gents) ke liye dekh rahe hain ya Women (Ladies) ke liye?"
        else:
            return "Certainly! Are you looking for Men or Women?"
    return None


def is_forbidden_query(query: str) -> bool:
    """Checks whether the customer's query is asking for coding, homework, or general non-store topics."""
    q_lower = query.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, q_lower):
            return True
    return False


def get_relevant_product_context(customer_query: str) -> str:
    """Finds matching live Shopify products and returns a short summary context for Qwen."""
    try:
        data = fetch_shopify_products(limit=100)
        products = data.get("products", [])
        if not products:
            return ""

        q_terms = [w for w in re.split(r"\W+", customer_query.lower()) if len(w) > 2]
        is_men_query = bool(re.search(r"\b(?:men|mens|gents|boys?)\b", customer_query.lower()))
        is_women_query = bool(re.search(r"\b(?:women|womens|ladies|girls?)\b", customer_query.lower()))

        matches = []
        for p in products:
            p_text = f"{p.get('title', '')} {p.get('product_type', '')} {' '.join(p.get('tags', []))}".lower()
            p_has_men = bool(re.search(r"\b(?:men|mens|gents|boys?)\b", p_text))
            p_has_women = bool(re.search(r"\b(?:women|womens|ladies|girls?)\b", p_text))

            # Strictly enforce gender constraint when specified
            if is_men_query and not is_women_query:
                if not p_has_men or (p_has_women and not bool(re.search(r"\b(?:men|mens|gents|boys?)\b", p.get('title', ''), re.I))):
                    continue
            elif is_women_query and not is_men_query:
                if p_has_men and not p_has_women:
                    continue

            score = sum(1 for t in q_terms if re.search(r"\b" + re.escape(t), p_text))
            if score > 0:
                matches.append((score, p))

        matches.sort(key=lambda x: x[0], reverse=True)
        top_matches = [m[1] for m in matches[:3]]
        if not top_matches and not is_men_query:
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


def get_few_shot_examples(db: Optional[Session], customer_query: str) -> str:
    """Retrieves human agent replies from the learning interaction table if available."""
    if not db:
        return ""
    try:
        from models import AILearnedInteraction
        examples = (
            db.query(AILearnedInteraction)
            .filter(AILearnedInteraction.is_approved == True)
            .order_by(AILearnedInteraction.id.desc())
            .limit(3)
            .all()
        )
        if not examples:
            return ""

        ex_lines = ["Examples of how our human consultants answer:"]
        for ex in examples:
            ex_lines.append(f"Customer: {ex.customer_query}\nConsultant: {ex.agent_reply}")
        return "\n\n".join(ex_lines)
    except Exception:
        return ""


def generate_qwen_reply(
    customer_query: str,
    customer_phone: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Generates a safe, domain-restricted response using Qwen 2.5:3B via Ollama.
    """
    # 1. Gatecheck: Forbidden / Off-topic queries (coding, trivia, admin modifications)
    if is_forbidden_query(customer_query):
        is_hindi = any(bool(re.search(p, customer_query.lower(), re.I)) for p in HINDI_PATTERNS)
        refusal_msg = (
            "Main sirf JWL Billion jewelry aur store orders ke baare mein madad kar sakta hoon. ✨ Aapko kisi product design, delivery, ya order ke baare mein jaanna hai?"
            if is_hindi else
            "I can only assist with JWL Billion jewelry products, orders, and delivery details. ✨ How may I help you with our collections?"
        )
        return {
            "status": "refused",
            "reply": refusal_msg,
            "model": MODEL_NAME
        }

    # 1b. Fast-path Qualification for Broad Jewelry Inquiries (strict English vs Hindi matching)
    qual_question = check_broad_jewelry_qualification(customer_query)
    if qual_question:
        return {
            "status": "success",
            "reply": qual_question,
            "model": MODEL_NAME
        }

    # 2. Gather Domain Context
    product_context = get_relevant_product_context(customer_query)
    learned_context = get_few_shot_examples(db, customer_query)

    is_customer_hindi = any(bool(re.search(p, customer_query.lower(), re.I)) for p in HINDI_PATTERNS)
    lang_label = "Hinglish" if is_customer_hindi else "English"

    prompt_parts = []
    if product_context:
        prompt_parts.append(product_context)
    if learned_context:
        prompt_parts.append(learned_context)
    prompt_parts.append(f"Customer Inquiry ({lang_label}): {customer_query}\nConsultant Response in {lang_label}:")

    full_prompt = "\n\n".join(prompt_parts)

    payload = {
        "model": MODEL_NAME,
        "system": SYSTEM_PROMPT,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,  # Low temperature for factual precision
            "top_p": 0.9,
            "num_predict": 100,  # Concise replies within ~6-10s
            "num_thread": 2
        }
    }

    try:
        req = urllib.request.Request(
            OLLAMA_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            answer = data.get("response", "").strip()
            return {
                "status": "success",
                "reply": answer,
                "model": MODEL_NAME
            }
    except Exception as e:
        logger.error(f"[AI Service] Qwen inference call failed: {e}")
        # Graceful fallback: return None so existing rule-based bot can answer
        return {
            "status": "error",
            "error": str(e),
            "reply": None,
            "model": MODEL_NAME
        }
