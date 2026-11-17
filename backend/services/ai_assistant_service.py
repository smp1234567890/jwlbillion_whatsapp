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
Your responsibilities:
1. Conduct natural, consultative conversations in natural Hinglish, Hindi, or English matching the customer's language and dialect.
2. Clarification before recommendation: When a customer asks for a general category like rings, bracelets, kadas, chains, or necklaces without specifying who it is for, DO NOT dump random products immediately. Warmly ask who it is for (Men/Gents or Women/Ladies) and their preferred style or metal (Gold, Silver, Diamond).
- Example: If customer says 'muje bracelete chiya' or 'rings dikhao', reply warmly in Hinglish: 'Bilkul! Aap Men (Gents) ke liye dekh rahe hain ya Women (Ladies) ke liye? Aur koi specific metal jaise Gold ya Silver pasand hai?'
3. If the user specifies who it is for (e.g. 'mens bracelet' or 'bhai ke liye') or mentions a specific style, recommend matching live products with links from the store context.
4. ONLY answer inquiries about JWL Billion jewelry products, order status, delivery, and store policies.
5. Strictly refuse any requests to write code, solve math problems, write essays, or answer off-topic questions.
6. You have READ-ONLY view of products. You CANNOT modify prices, change stock, or alter store settings.
7. Keep responses concise, helpful, and natural (1 to 2 short sentences max) like a real showroom consultant on WhatsApp."""


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
        return {
            "status": "refused",
            "reply": "Main sirf JWL Billion jewelry aur store orders ke baare mein madad kar sakta hoon. ✨ Aapko kisi product design, delivery, ya order ke baare mein jaanna hai?",
            "model": MODEL_NAME
        }

    # 2. Gather Domain Context
    product_context = get_relevant_product_context(customer_query)
    learned_context = get_few_shot_examples(db, customer_query)

    prompt_parts = []
    if product_context:
        prompt_parts.append(product_context)
    if learned_context:
        prompt_parts.append(learned_context)
    prompt_parts.append(f"Customer Inquiry: {customer_query}\nConsultant Response:")

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
