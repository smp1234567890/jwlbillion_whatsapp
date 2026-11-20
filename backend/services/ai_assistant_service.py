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


def _clean_product_photo(product: dict) -> Optional[str]:
    """
    Selects a clean, aesthetic product photo.
    Filters out measurement scales, ruler markings, cm grids, and internal QA shots.
    """
    images = product.get("all_images") or product.get("images") or []
    img_urls = []
    for im in images:
        if isinstance(im, dict):
            u = im.get("src")
            if u: img_urls.append(u)
        elif isinstance(im, str):
            img_urls.append(im)
    if not img_urls and product.get("image_url"):
        img_urls = [product["image_url"]]
    if not img_urls:
        return None

    clean_photos = []
    for u in img_urls:
        fn = u.split("/")[-1].split("?")[0].lower()
        if any(bad in fn for bad in [
            "scale", "ruler", "measurement", "cm_",
            "wa0060", "wa0006", "wa0011", "wa0019", "wa0020", "wa0021"
        ]):
            continue
        clean_photos.append(u)

    return clean_photos[0] if clean_photos else img_urls[0]

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

SALES_SYSTEM_PROMPT = """You are a warm, respectful and highly knowledgeable female personal jewelry stylist for JWL Billion (jwlbillion.com).
JWL Billion crafts premium jewelry for BOTH Men and Women (Men's Kadas/Bracelets, Chains, Rings, and Women's Necklaces, Earrings, Bangles) with premium gold-plated, silver-finish, American Diamond / CZ jewelry (₹300–₹2,000).
CRITICAL: We DO have a complete Men's Jewelry collection! NEVER say we only have ladies jewelry or that we don't have men's jewelry.

MANDATORY DIRECTIVE - ALWAYS DIRECT CUSTOMERS TO VISIT THE WEBSITE (jwlbillion.com):
- In EVERY response, actively urge and guide the customer to visit our official website: https://jwlbillion.com (or the specific product/collection link).
- Frame the website as the ultimate place to see all HD real product videos, explore 500+ trending designs, read verified buyer reviews, and place orders with 100% Cash on Delivery (COD) & free delivery!
- Strong call-to-action examples:
  * "Aap hamari official website https://jwlbillion.com par visit karke saare trending designs aur live videos dekh sakte hain!"
  * "Is design ko website par dekhne aur direct Cash on Delivery order karne ke liye yahan tap karein: [Link]"
  * "Baki ke saare collection dekhne ke liye abhi visit kijiye: https://jwlbillion.com"

CORE CONVERSATIONAL SELLING PRINCIPLES (HIGH CONVERSION):
0. PERSONAL RELATABILITY & STORYTELLING (THE ULTIMATE CONVERSION DRIVER):
   - Always relate to the customer personally before or while presenting designs. Share a short, warm, relatable personal experience!
   - WEDDING / GIFTING:
     * If they ask for wedding/shadi gifts: Relate personally! Say: "Arey bohot badhiya! Maine bhi abhi recently apne cousin/bhai/behen ki wedding mein yeh set gift kiya tha, sabko iska royal sparkle aur finishing bohot pasand aaya tha!"
     * If buying for wife/husband/fiancé/partner: Relate warmly! (e.g. "Gift ke liye yeh bohot hi pyaara aur thoughtful choice hai, unhe 100% pasand aayega!").
     * If buying for mother/sister: Relate with family warmth! (e.g. "Maine apni mummy/sister ko bhi yeh design diya tha, daily wear ke saath traditional outfits dono pe bohot graceful lagta hai.").
   - DAILY WEAR / OFFICE WEAR:
     * Relate with practical comfort: "Main khud daily use ke liye lightweight chains prefer karti hoon, yeh bilkul comfortable rehti hai aur shine safe rehti hai."
   - CELEBRATION / OCCASION:
     * Always congratulate or celebrate their occasion genuinely first!

1. SOUND HUMAN & TALK LIKE A REAL JEWELLERY STORE CONSULTANT (NOT A SEARCH ENGINE):
   - Never sound like a robotic catalog index or automated bot.
   - Do NOT dump a list of 3-4 raw catalog titles with long links if the customer just said a single word like "chain", "ring", or "earrings".
   - IF THE CUSTOMER'S REQUEST IS BROAD/VAGUE (e.g. "chain dikhao", "earrings", "designs", "latest"):
     Share 1-2 top designs with links, and always guide them to check the full collection on the website https://jwlbillion.com.
   - IF GENDER/STYLE IS ALREADY KNOWN (e.g., "women plain long chain"):
     Present 1 or at most 2 best-matching pieces in natural spoken words with their link, and invite them to explore more on the site.

2. PRESENT PRODUCTS LIKE A HUMAN STYLIST (NO ROBOTIC TITLES):
   - NEVER copy-paste long, SEO-stuffed Shopify catalog titles verbatim (e.g., instead of "Golden Grace Gold-Plated Chain Necklace for Women – Minimalist Lightweight Everyday & Party Wear Jewellery - ₹999.00", write: "Yeh hamari Golden Grace lightweight gold-plated chain hai (₹999) — daily wear ke liye perfect hai aur iska finish bilkul real gold jaisa lagta hai.").
   - Highlight 1 key emotional benefit (lightweight, real look, daily wear, royal sparkle).
   - Frame the link cleanly and helpfully to drive website clicks: "Aap iska video aur customer reviews website par dekh sakte hain: [Link]" or "Website par details dekhne ke liye tap karein: [Link]".

3. REASSURE TRUST & WEAVE CASH ON DELIVERY (COD) NATURALLY:
   - Remember that customers will order on the website, but their biggest hesitation is fraud, quality fear, or payment trust.
   - Naturally reassure: Cash on Delivery (COD) is available, 7-day easy replacement policy, and quality guarantee.
   - Example: "Website par Cash on Delivery (COD) available hai, toh aap delivery ke time parcel aaram se check kar sakte hain."

4. NO HIGH-PRESSURE SALES OR FALSE PROMISES:
   - Be completely transparent and respectful. NEVER claim fake gold karat (NEVER say 18K/22K/24K; always say "premium gold-plated finish").
   - CRITICAL ON WARRANTY & CLAIMS: Fashion/imitation jewelry does not carry a time-bound warranty (NEVER say 1 year or 6 months warranty). Explain politely that with normal care (keeping away from water and perfume), the shine stays beautiful for a long time, and we provide 7-day easy replacement if any defect is found on delivery.

5. PERSONA & LANGUAGE MIRRORING:
   - You represent JWL Billion. You are a woman, so ALWAYS speak as a woman using feminine polite grammar ("karti hoon", "bataungi", "samajh sakti hoon").
   - DO NOT USE ANY PERSONAL NAME. Do NOT say "My name is Riya/Maya" or introduce yourself with a personal name.
   - ALWAYS MIRROR THE CUSTOMER'S LANGUAGE:
     * Gujarati -> Warm Gujarati ("Kem cho, tame aaje shu jova mango cho?")
     * Hindi / Devanagari -> Natural Hindi
     * Hinglish -> Fluent Roman Hinglish
     * Marathi, Bengali, Tamil, Telugu, English -> Mirror accordingly!
   - Use respectful pronouns ("Aap", "Tame").
   - Keep messages concise, conversational (2 to 3 short natural sentences), always driving the customer to check the website (https://jwlbillion.com)."""


def is_forbidden_query(query: str) -> bool:
    """Checks whether the query is off-topic (coding, hacking, trivia)."""
    q_lower = query.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, q_lower):
            return True
    return False


def get_recent_chat_history(sender_phone: str, db: Optional[Session], limit: int = 15) -> str:
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
            sender = "Customer" if m.sender_type == "CUSTOMER" else "JWL Stylist"
            body = (m.text or "").strip()
            # If customer or message tagged/quoted another message, surface it in the history
            if m.quoted_message and isinstance(m.quoted_message, dict) and m.quoted_message.get("text"):
                q_txt = m.quoted_message.get("text", "")[:80]
                body = f"[Replying to: \"{q_txt}\"] {body}".strip()
            if body and not body.startswith("Sent interactive"):
                history_lines.append(f"{sender}: {body}")
        
        return "\n".join(history_lines)
    except Exception as e:
        logger.warning(f"[AI Service] Error loading chat history: {e}")
        return ""


JEWELRY_CATEGORY_CANONICAL = {
    "bracelet": [r"\b(?:bracelets?|bracelete?|breslets?|breslete?|braclets?|wristlets?|kadas?|kade|kara|cuff)\b", r"ब्रेसलेट|कड़ा"],
    "bangle": [r"\b(?:bangles?|banglez|chudi|choodi|choodiyan|chudiya|kangan|bangals?|bangels?)\b", r"चूड़ी|कंगन|बैंगल|बेंगल"],
    "anklet": [r"\b(?:anklets?|payals?|pajeb|panjeb|pair\s*ke)\b", r"पायल|पाजेब|एंक्लेट"],
    "ring": [r"\b(?:rings?|ringss?|anguthi|anguthiyan|anguti|chhalla)\b", r"(?<![a-zA-Z\u0900-\u097F])(?:अंगूठी|रिंग)(?![a-zA-Z\u0900-\u097F])"],
    "chain": [r"\b(?:chains?|chane|chaines?|chen|chene|cene|chainke|chenke|chainka)\b", r"ચૈન|ચેન|चैन|चेन"],
    "necklace": [r"\b(?:necklaces?|necjlace?|haar|haars?|choker|mangalsutra|pendant|pendants?|pendent|gale\s*ka|gale\s*ki|gale\s*ke)\b", r"હાર|हार|नेकलेस|पेंडेंट|गले\s*का|गले\s*की"],
    "earring": [r"\b(?:earrings?|ear\s*rings?|jhumk[ai]|jhumkhe|balis?|studs?|ear?nings?|errings?|earings?)\b", r"ઇયરરિંગ|झुमका|बाली|इयररिंग|इयरिंग्स|झुमके"],
    "set": [r"\b(?:sets?|combo|combos?|jewellery\s*sets?|necklace\s*sets?|complete\s*set)\b", r"સેટ|सेट"]
}


DUAL_GENDER_CATEGORIES = {"chain", "bracelet", "kada", "ring"}


def get_relevant_product_context(customer_query: str, chat_history: str = "") -> tuple[str, list[dict]]:
    """Finds matching live Shopify products based on query and customer conversation history."""
    try:
        data = fetch_shopify_products(limit=250)
        products = data.get("products", [])
        if not products:
            return "", []

        # Check if customer inquiry references a quoted message with a product URL or title
        # E.g. [Replying to: "...ruby-elegance-gold-plated-jewelry-set"] This one
        quoted_url_match = re.search(r"https?://[^\s\"')]+", customer_query)
        if not quoted_url_match and chat_history:
            # Check last quoted message in history
            quoted_url_match = re.search(r"\[Replying to: [^\]]*(https?://[^\s\"')]+)", chat_history)

        if quoted_url_match:
            target_url = quoted_url_match.group(0).rstrip("/").lower()
            slug = target_url.split("/")[-1]
            exact_prod = next(
                (p for p in products if slug and slug in (p.get("product_url") or "").lower()),
                None
            )
            if exact_prod:
                lines = [
                    "Tagged Product Identified from Customer Swipe/Reply:",
                    f"- {exact_prod.get('title')}: ₹{exact_prod.get('price')} | Product Link: {exact_prod.get('product_url')}"
                ]
                return "\n".join(lines), [exact_prod]

        # Isolate customer's own utterances from chat history (ignore Riya's / Maya's bot replies to avoid self-contamination)
        customer_history_lines = [
            re.sub(r"^(?:Customer|User):\s*", "", line, flags=re.I).strip()
            for line in chat_history.splitlines()
            if re.match(r"^(?:Customer|User):", line, flags=re.I)
        ]
        customer_history_text = " ".join(customer_history_lines).lower()
        q_lower = (customer_query or "").lower()

        # 1. Detect categories requested in current query first
        query_categories = set()
        for cat_name, patterns in JEWELRY_CATEGORY_CANONICAL.items():
            for pat in patterns:
                if re.search(pat, q_lower, re.IGNORECASE):
                    query_categories.add(cat_name)
                    break

        # Fallback to customer's past statements only if current query mentions no category
        history_categories = set()
        if not query_categories and customer_history_text:
            for cat_name, patterns in JEWELRY_CATEGORY_CANONICAL.items():
                for pat in patterns:
                    if re.search(pat, customer_history_text, re.IGNORECASE):
                        history_categories.add(cat_name)
                        break

        active_categories = query_categories or history_categories

        # 2. Gender detection with multilingual and negation awareness
        # Supports English, Roman Hinglish, Devanagari Hindi, and Gujarati
        combined_customer_text = f"{customer_history_text} {q_lower}".strip()

        # Check for explicit negation of women/ladies
        women_negated = bool(re.search(
            r"\b(?:ladies|women|aurat|ladki|girls?|महिला|औरत|लड़कियों)\s*(?:nahi|not|mat|no|dont|don't|chahiye\s*nahi|નથી|નહિ)\b|"
            r"\b(?:nahi|not|no|dont|don't|નથી)\s*(?:chahiye\s*)?(?:ladies|women|aurat|girls?|महिला)\b",
            combined_customer_text, re.I
        ))
        men_negated = bool(re.search(
            r"\b(?:men|mens|gents|mard|boys?|पुरुष|मर्द|મેન્સ|પુરુષ)\s*(?:nahi|not|mat|no|dont|don't|chahiye\s*nahi|નથી|નહિ)\b|"
            r"\b(?:nahi|not|no|dont|don't|નથી)\s*(?:chahiye\s*)?(?:men|mens|gents)\b",
            combined_customer_text, re.I
        ))

        is_men = (
            bool(re.search(r"\b(?:men|mens|male|mard|gents|boys?|husband|bhai)\b", combined_customer_text, re.I))
            or bool(re.search(r"(?:मेन्स|मेंस|जेंट्स|मर्द|लड़कों|आदमी|पुरुष|મેન્સ|પુરુષ)", combined_customer_text))
        ) and not men_negated

        is_women = (
            bool(re.search(r"\b(?:women|womens|ladies|ledis|ladis|ledies|girls?|female|aurat|wife|sister|didi|jhumk[ai]|jhumkhe|payal|mangalsutra|chudi|choodi|kangan|anklets?)\b", combined_customer_text, re.I))
            or bool(re.search(r"(?:लेडीज|महिला|औरत|लड़कियों|મહિલા|લેડીઝ|झुमका|झुमकी|पायल|मंगलसूत्र|चूड़ी|कंगन)", combined_customer_text))
        ) and not women_negated

        # If ladies/women was explicitly negated, reinforce men
        if women_negated:
            is_women = False
            is_men = True

        # Option A Proactive Qualification:
        # If the customer is asking for a category that exists for BOTH Men & Women (e.g. chains, bracelets, kadas, rings)
        # and has NOT yet specified whether it's for Men or Women, DO NOT return products yet!
        # This prevents sending mixed men/women photos before qualifying the customer.
        is_dual_gender = bool(active_categories and active_categories.intersection(DUAL_GENDER_CATEGORIES))
        if is_dual_gender and not is_men and not is_women:
            return "", []

        is_both = (is_men and is_women) or bool(re.search(r"\b(?:both|dono|donon|sab|sabhi)\b|(?:दोनों|બંને)", combined_customer_text, re.I))

        matches = []
        for p in products:
            p_title = p.get("title", "").lower()
            p_type = (p.get("product_type") or "").lower()
            p_tags = " ".join(p.get("tags", [])).lower()
            p_text = f"{p_title} {p_type} {p_tags}"

            p_has_men = bool(re.search(r"\b(?:men|mens|gents|boys?)\b", p_text))
            p_has_women = bool(re.search(r"\b(?:women|womens|ladies|girls?)\b", p_text))

            # Filter out opposite gender when explicitly specified (unless both was requested)
            if is_both:
                pass
            elif is_men and not is_women:
                if not p_has_men or (p_has_women and not bool(re.search(r"\b(?:men|mens|gents)\b", p_title))):
                    continue
            elif is_women and not is_men:
                if p_has_men and not p_has_women:
                    continue

            # Category score
            cat_score = 0
            if active_categories:
                for cat in active_categories:
                    multiplier = 30 if cat in query_categories else 15
                    if cat == "bracelet" and ("bracelet" in p_text or "kada" in p_text or p_type in ["bracelet", "kada"]):
                        cat_score += multiplier
                    elif cat == "bangle" and ("bangle" in p_text or "chudi" in p_text or "kangan" in p_text or p_type in ["bangle"]):
                        cat_score += multiplier
                    elif cat == "anklet" and ("anklet" in p_text or "payal" in p_text or p_type == "anklet"):
                        cat_score += multiplier
                    elif cat == "ring" and ("ring" in p_text or p_type == "ring") and "earring" not in p_text:
                        cat_score += multiplier
                    elif cat == "necklace" and ("necklace" in p_text or "pendant" in p_text or "choker" in p_text or p_type in ["necklace", "pendant"]):
                        cat_score += multiplier
                    elif cat == "chain" and ("chain" in p_text or p_type == "chain"):
                        cat_score += multiplier
                    elif cat == "earring" and ("earring" in p_text or "jhumka" in p_text or "bali" in p_text or p_type == "earrings"):
                        cat_score += multiplier
                    elif cat == "set" and ("set" in p_text or p_type in ["set", "jewelry set", "jewellery set"]):
                        cat_score += multiplier
            
            # If a specific category was detected, reject products that don't match it
            if active_categories and cat_score == 0:
                continue

            # Keyword score: ignore generic words like 'jewellery', 'jewelry', 'collection', 'design', etc.
            STOP_TERMS = {"jewellery", "jewelry", "collection", "product", "products", "item", "items", "good", "acchi", "achhi", "best", "dekh", "rahe", "hain", "liye", "kharidne"}
            q_terms = [w for w in re.split(r"\W+", q_lower) if len(w) > 2 and w not in STOP_TERMS]
            text_score = sum(3 if re.search(r"\b" + re.escape(t), p_title) else 1 for t in q_terms if re.search(r"\b" + re.escape(t), p_text))

            total_score = cat_score + text_score
            matches.append((total_score, p))

        # Filter out products that have zero relevance score
        valid_matches = [m for m in matches if m[0] > 0]

        # If customer explicitly asked for Men's or Women's jewelry without a specific category (e.g. "Male friends", "Gents ke liye"),
        # provide the top bestsellers for that gender so the AI doesn't hallucinate fake items or fall back to generic links!
        if not valid_matches and (is_men or is_women) and not active_categories:
            gender_matches = []
            for p in products:
                p_title = p.get("title", "").lower()
                p_type = (p.get("product_type") or "").lower()
                p_tags = " ".join(p.get("tags", [])).lower()
                p_text = f"{p_title} {p_type} {p_tags}"
                p_has_men = bool(re.search(r"\b(?:men|mens|gents|boys?)\b", p_text))
                p_has_women = bool(re.search(r"\b(?:women|womens|ladies|girls?)\b", p_text))

                if is_men and not is_women:
                    if p_has_men and not (p_has_women and not bool(re.search(r"\b(?:men|mens|gents)\b", p_title))):
                        gender_matches.append((10, p))
                elif is_women and not is_men:
                    if p_has_women and not (p_has_men and not bool(re.search(r"\b(?:women|womens|ladies)\b", p_title))):
                        gender_matches.append((10, p))
            valid_matches = gender_matches

        # Prioritize mid-range (₹500–₹1,200) options first as recommended bestsellers;
        # do not pitch entry-level / cheap items (< ₹400) first unless customer explicitly asks for low budget.
        is_low_budget_inquiry = bool(re.search(r"\b(?:sasta|kam\s*budget|cheap|low\s*price|200|300)\b", combined_customer_text))
        def product_rank(item):
            relevance, prod = item
            try:
                pr = float(prod.get("price") or 0)
            except Exception:
                pr = 0
            if is_low_budget_inquiry:
                return (relevance, -pr)
            # Mid-range sweet spot: ₹500 - ₹999 gets highest priority (+20)
            if 500 <= pr <= 999:
                boost = 20
            elif 1000 <= pr <= 1500:
                boost = 12
            elif 400 <= pr < 500:
                boost = 5
            elif pr > 1500:
                boost = 3
            else: # Entry-level items (< ₹400) ranked lower
                boost = -15
            return (relevance + boost, -abs(pr - 750))

        # If customer asks for "dusra", "aur", "other", "next", deprioritize or exclude items already shown in chat history!
        is_another_request = bool(re.search(r"\b(?:dusra|dusri|doosra|doosri|aur\s*dikhao|aur\s*dekhao|aur\s*dekhna|aur\s*dekhana|aur\s*bhejo|aur\s*batao|next|another|other|different|more)\b", q_lower))
        if is_another_request and chat_history:
            # Filter out or push down products whose titles already appeared in the conversation history
            unseen_matches = []
            seen_matches = []
            for item in valid_matches:
                p_title_clean = (item[1].get("title") or "").strip().lower()
                if p_title_clean and p_title_clean in chat_history.lower():
                    seen_matches.append((item[0] - 50, item[1]))
                else:
                    unseen_matches.append(item)
            valid_matches = unseen_matches + seen_matches

        valid_matches.sort(key=product_rank, reverse=True)
        top_matches = [m[1] for m in valid_matches[:3]]

        lines = ["Available Live Store Products:"]
        for p in top_matches:
            price_val = p.get("price") or "Price on inquiry"
            prod_link = p.get("product_url") or p.get("shop_url") or "https://jwlbillion.com"
            lines.append(f"- {p.get('title')}: ₹{price_val} | Product Link: {prod_link}")
        return "\n".join(lines) if top_matches else "", top_matches
    except Exception as e:
        logger.warning(f"[AI Service] Error loading product context: {e}")
        return "", []


def _call_gemini_api(system_prompt: str, user_prompt: str, api_key_override: Optional[str] = None) -> Optional[str]:
    """
    Calls Google Gemini Flash API for high-accuracy, fluent Roman Hinglish generation.
    Supports automatic model fallback if a specific model returns 404 (e.g. legacy model deprecations).
    Returns the generated response string, or None if the request fails or key is missing.
    """
    api_key = api_key_override or getattr(config, "GEMINI_API_KEY", None) or ""
    if not api_key:
        return None

    configured_model = getattr(config, "GEMINI_MODEL", "gemini-2.5-flash")
    # Candidate models to try in order (handles project-specific access differences)
    candidate_models = [configured_model]
    for alt in ["gemini-3.5-flash-lite", "gemini-2.5-flash"]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 800
        }
    }

    data_bytes = json.dumps(payload).encode("utf-8")

    for model in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
        except urllib.error.HTTPError as he:
            # If 404 model not found for this key, try the next candidate model
            if he.code == 404:
                continue
            logger.warning(f"[AI Service] Gemini ({model}) HTTP Error {he.code}: {he.read().decode('utf-8')[:200]}")
            break
        except Exception as e:
            logger.warning(f"[AI Service] Gemini ({model}) API call failed: {e}")
            break

    return None


def _call_openai_api(system_prompt: str, user_prompt: str) -> Optional[str]:
    """
    Calls OpenAI ChatGPT (gpt-4o-mini) as the primary sales stylist engine.
    Exceptional instruction-following, objection handling, and Roman Hinglish fluency.
    """
    api_key = getattr(config, "OPENAI_API_KEY", None) or ""
    if not api_key:
        return None

    model = getattr(config, "OPENAI_MODEL", "gpt-4o-mini")
    url = "https://api.openai.com/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.3
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.warning(f"[AI Service] OpenAI API call failed: {e}")
    return None


def transcribe_voice_with_sarvam(audio_file_path: str) -> Optional[dict]:
    """
    Transcribes & translates WhatsApp audio/voice notes across 23 Indian languages using Sarvam AI Saaras model.
    Returns a dict with:
      - transcript: original transcript in native script (Hindi, Gujarati, Tamil, etc.)
      - translated: clear English translation for accurate ChatGPT understanding
      - language_code: detected language (e.g., 'gu-IN', 'hi-IN', 'ta-IN')
    """
    api_key = getattr(config, "SARVAM_API_KEY", None) or ""
    if not api_key or not audio_file_path:
        return None

    try:
        import os, requests
        if not os.path.exists(audio_file_path):
            return None

        url = "https://api.sarvam.ai/speech-to-text"
        headers = {"api-subscription-key": api_key}
        filename = os.path.basename(audio_file_path)

        # 1. Fetch direct translation to English (works across all 23 Indian languages)
        translated_text = ""
        lang_code = ""
        with open(audio_file_path, "rb") as f:
            files = {"file": (filename, f, "audio/ogg")}
            data = {"model": "saaras:v3", "mode": "translate"}
            resp = requests.post(url, headers=headers, data=data, files=files, timeout=15)
            if resp.status_code == 200:
                res_json = resp.json()
                translated_text = res_json.get("transcript", "").strip()
                lang_code = res_json.get("language_code", "")

        # 2. Fetch original native transcription
        native_text = ""
        with open(audio_file_path, "rb") as f:
            files = {"file": (filename, f, "audio/ogg")}
            data = {"model": "saaras:v3", "mode": "transcribe"}
            resp2 = requests.post(url, headers=headers, data=data, files=files, timeout=15)
            if resp2.status_code == 200:
                native_text = resp2.json().get("transcript", "").strip()

        final_transcript = native_text or translated_text
        if not final_transcript:
            return None

        logger.info(f"[Sarvam ASR] Lang={lang_code} | Native='{native_text}' | Translated='{translated_text}'")
        return {
            "transcript": final_transcript,
            "translated": translated_text,
            "language_code": lang_code
        }
    except Exception as e:
        logger.warning(f"[Sarvam ASR] Error transcribing voice note: {e}")
    return None


def _call_groq_api(system_prompt: str, user_prompt: str) -> Optional[str]:
    """
    Calls Groq Cloud API as high-speed fallback with fluent Hinglish capabilities.
    Returns the generated response string, or None if the request fails or key is missing.
    """
    api_key = getattr(config, "GROQ_API_KEY", None) or ""
    if not api_key:
        return None

    model = getattr(config, "GROQ_MODEL", "qwen/qwen3.8-27b")
    url = "https://api.groq.com/openai/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 400,
        "temperature": 0.3
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Mozilla/5.0"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.warning(f"[AI Service] Groq API call failed: {e}")
    return None


def generate_qwen_reply(
    customer_query: str,
    customer_phone: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Generates a natural, context-aware sales-converting reply using Qwen 2.5 via Ollama.
    """
    q_clean = (customer_query or "").strip().lower()

    # Retrieve recent chat history early so we know if the customer already defined what they want!
    chat_history = get_recent_chat_history(customer_phone, db, limit=15) if (customer_phone and db) else ""

    # Check if the customer previously stated their desired items in chat history
    has_prior_context = bool(chat_history and any(
        re.search(pat, chat_history, re.I)
        for pats in JEWELRY_CATEGORY_CANONICAL.values()
        for pat in pats
    ))

    # 00. Guard against single characters, typos, or gibberish (e.g. "H", "k", "??", "...")
    # Only show generic category ask if there is NO prior customer category in history!
    # If the customer already told us what they want (e.g. "Sets aur Earrings,Rings") or said "Dusra",
    # DO NOT ask them again what they want — let AI provide the next item from their requested categories!
    is_short_or_followup = (
        (len(q_clean) <= 2 and not re.match(r"^(?:hi|ok|hm|no|ji)$", q_clean))
        or bool(re.search(r"^\s*(?:dusra|dusri|aur|next|other|more|aur\s*dikhao|aur\s*dekhao|aur\s*dekhna|aur\s*dekhana|aur\s*bhejo|aur\s*batao|kuch\s*aur)\s*$", q_clean, re.I))
    )
    if is_short_or_followup and not has_prior_context:
        clarify_short = "Ji, kahiye! 😊 Aap kis type ki jewellery dekh rahe hain — jaise Earrings, Necklace, Rings ya Bracelets?"
        return {"status": "success", "reply": clarify_short, "model": "playbook"}

    # 0a. Instant Fast-Path for Meta Ads Default Inbound ("Hello! Can I get more info on this?")
    # Default greeting directly welcomes the user and asks how to help without invoking AI
    if re.search(r"^(?:hello!?\s*)?can\s*i\s*get\s*more\s*info\s*(?:on\s*this)?\??$", q_clean):
        welcome_hinglish = (
            "Namaste! Welcome to JWL Billion ✨\n\n"
            "Main aapki kya madad kar sakti hoon? Aap koi specific jewellery dekh rahe hain ya latest collection explore karna chahenge?"
        )
        return {"status": "success", "reply": welcome_hinglish, "model": "default-greeting"}

    # 0b. Fast-Path for Generic Photo Requests without category ("Pic bhejiye", "Photos bhejo", "Design dikhao", "aap design bhje")
    # Clarify which jewelry piece the customer would like to see instead of dumping random pendants or scale photos
    is_generic_photo_request = (
        bool(re.search(r"\b(?:designs?|dijan|डिज़ाइन|डिजाइन|फोटो|photo|photos?|pics?|tasveer)\b", q_clean, re.I))
        and bool(re.search(r"\b(?:bhej\w*|bhj\w*|dikha\w*|dekha\w*|send|share|karo|do|दिखाओ|भेजो|दीजिए|दे)\b", q_clean, re.I))
        and not any(re.search(pat, q_clean, re.I) for pats in JEWELRY_CATEGORY_CANONICAL.values() for pat in pats)
    )
    if is_generic_photo_request:
        photo_ask = "Haan ji, bilkul share karti hoon! 😊 Aapko kis category ke designs dekhne hain — jaise Earrings, Necklaces/Chains, Bangles, ya Bracelets?"
        return {"status": "success", "reply": photo_ask, "model": "playbook"}

    # 0c. Fast-Path for Acknowledgements, Sign-offs & Thank Yous ("ok thanks", "thank you", "dhanyawad", "bye", "by", "byy")
    if re.search(r"^\s*(?:ok\s*)?(?:thanks?|thank\s*you|shukriya|dhanyawad|welcome|ok\s*bye|bye+|by+|good\s*night|alvida|tc|take\s*care)\s*!*\s*$", q_clean):
        thanks_reply = "Most welcome ji! 😊 Aapka din shubh rahe. Jab bhi koi naya design dekhna ho, bas message kar dijiyega!"
        return {"status": "success", "reply": thanks_reply, "model": "playbook"}

    if re.search(r"^\s*(?:ok\s*)?(?:koi\s*(?:nhi|nahi|baat\s*nhi|baat\s*nahi)|it['’]?s\s*ok|no\s*problem|koi\s*na)\s*!*\s*$", q_clean):
        koi_nhi_reply = "Koi baat nahi ji! 😊 Jab bhi aapka mann ho ya kuch specific pasand aaye, aap aaram se bata sakte hain. Have a great day!"
        return {"status": "success", "reply": koi_nhi_reply, "model": "playbook"}

    if re.search(r"^\s*(?:ok|okay|thik\s*hai|theek\s*hai|achha|acha|accha|h[ao]ji|hmm|hm)\s*!*\s*$", q_clean):
        ok_reply = "Bilkul ji! 😊 Aap araam se collection dekhiye, main yahin hoon."
        return {"status": "success", "reply": ok_reply, "model": "playbook"}

    # 0d. Fast-Path for How are you / Kaise ho
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
    if re.search(r"\b(?:warrenty|warranty|garanty|guarantee)\b|(?:गारंटी|वारंटी)", q_clean, re.I):
        if re.search(r"[\u0900-\u097F]", customer_query):
            warranty_reply = (
                "हमारी फैशन ज्वेलरी पर कोई 1 साल की टाइम-बाउंड वारंटी नहीं होती है। 😊 "
                "लेकिन डिलीवरी के समय पार्सल में कोई भी डिफेक्ट या डैमेज मिले, तो 7-दिन का आसान रिप्लेसमेंट/एक्सचेंज मिलता है! "
                "साथ ही 100% Cash on Delivery (COD) उपलब्ध है ताकि आप डिलीवरी पर सुरक्षित रूप से पार्सल देख सकें।"
            )
        elif re.search(r"[\u0A80-\u0AFF]", customer_query):
            warranty_reply = (
                "અમારી ફેશન જ્વેલરી પર કોઈ 1 વર્ષની ટાઈમ-બાઉન્ડ વોરંટી નથી હોતી. 😊 "
                "પણ ડિલિવરી વખતે જો પાર્સલમાં કોઈ ડિફેક્ટ હોય તો 7-દિવસનું ઇઝી રિપ્લેસમેન્ટ/એક્સચેન્જ મળે છે! "
                "સાથે 100% Cash on Delivery (COD) પણ ઉપલબ્ધ છે."
            )
        else:
            warranty_reply = (
                "Hamari fashion jewellery par koi 1 saal ya time-bound warranty nahi hoti hai. 😊 "
                "Lekin delivery ke waqt agar parcel mein koi defect ya damage mile, "
                "toh 7-day easy replacement/exchange milta hai! Saath hi 100% Cash on Delivery (COD) bhi available hai taaki aap delivery par safely parcel dekh sakein."
            )
        return {"status": "success", "reply": warranty_reply, "model": "playbook"}

    is_fade_or_tarnish_inquiry = bool(re.search(
        r"\b(?:fade|color\s*fade|colour\s*fade|kaal[aieo]|kal[aieo]|rang\s*(?:nikal|uth|fade|chala)|tarnish|color\s*chala|colour\s*chala)\b|(?:काले|काला|काली|काळा|કળા|કાળી|કાળા|कलर\s*चला)",
        q_clean, re.I
    ))
    if is_fade_or_tarnish_inquiry:
        if re.search(r"[\u0900-\u097F]", customer_query):
            fade_reply = "जी बिल्कुल नहीं! 😊 इसमें मल्टी-लेयर प्रीमियम गोल्ड-प्लेटेड फिनिश होती है जिससे यह आसानी से काली नहीं पड़ती। बस इसे पानी, पसीने और परफ्यूम से बचाकर रखें तो इसकी चमक और पॉलिश लंबे समय तक बिल्कुल नई जैसी बनी रहती है! ❤️"
        elif re.search(r"[\u0A80-\u0AFF]", customer_query):
            fade_reply = "જી બિલકુલ નહીં! 😊 આમાં મલ્ટી-લેયર પ્રીમિયમ ગોલ્ડ-પ્લેટેડ ફિનિશ હોય છે જેથી તે કાળી પડતી નથી. બસ પાણી અને પરફ્યુમથી દૂર રાખો તો ચમક લાંબા સમય સુધી સચવાઈ રહે છે! ❤️"
        else:
            fade_reply = "Ji bilkul nahi, yeh kaale nahi honge! 😊 Ismein multi-layer premium gold-plated finish hoti hai. Bas direct paani aur perfume se bacha kar rakhein toh iski shine aur polish lambe time tak bilkul nayi jaisi rehti hai! ❤️"
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

    # 0c. Jhumki / Traditional Dome Jhumka Clarification & Alternative (Option B)
    # JWL Billion specializes in modern western studs, hoops, and elegant drop/dangle earrings.
    # When customer asks for Jhumki, honestly clarify that traditional dome jhumkas aren't in stock,
    # and offer our top matching drop/dangle earrings as gorgeous alternatives with photos!
    is_jhumki_inquiry = bool(re.search(
        r"\b(?:jhumk[ai]|jhumkhe|jhumkas?|jhumkis?|chandbalis?)\b|(?:झुमका|झुमकी|झुमके|ઝુમકી|ઝુમકા)",
        customer_query, re.I
    ))
    if is_jhumki_inquiry:
        data_cat = fetch_shopify_products(limit=250)
        all_prods = data_cat.get("products", [])
        # Find elegant drop/dangle earrings to recommend as alternatives
        drop_alternatives = [
            p for p in all_prods
            if any(k in (p.get("title") or "").lower() for k in ["drop", "dangle"])
            and "earring" in (p.get("title") or "").lower()
            and float(p.get("price") or 0) >= 300
        ]
        chosen_drops = drop_alternatives[:2] if drop_alternatives else []
        chosen_first = chosen_drops[0] if chosen_drops else None
        first_img = _clean_product_photo(chosen_first) if chosen_first else None

        if re.search(r"[\u0900-\u097F]", customer_query):
            jhumki_reply = (
                "हमारे पास अभी ट्रेडिशनल डोम झुमकी उपलब्ध नहीं है जी। 😊 "
                "लेकिन हमारे पास बहुत ही सुंदर और क्लासिक ड्राप और डैंगल इयररिंग्स हैं जो ट्रेडिशनल और पार्टी वियर दोनों के साथ बहुत प्यारे लगते हैं! "
                "क्या आप इनमें से कोई स्टाइल देखना पसंद करेंगे?"
            )
        elif re.search(r"[\u0A80-\u0AFF]", customer_query):
            jhumki_reply = (
                "અમારી પાસે હમણાં ટ્રેડિશનલ ઝુમકી ઉપલબ્ધ નથી જી. 😊 "
                "પણ અમારી પાસે ખૂબ જ સુંદર અને ક્લાસી ડ્રોપ અને ડેંગલ ઇયરરિંગ્સ છે જે ટ્રેડિશનલ અને પાર્ટી વેર સાથે ખૂબ જ સરસ લાગે છે! "
                "શું તમે આ ડિઝાઇન્સ જોવા માંગો છો?"
            )
        else:
            jhumki_reply = (
                "Hamare paas abhi traditional dome jhumki uplabdh nahi hai ji. 😊 "
                "Lekin hamare paas bohot sundar drop aur dangle earrings hain jo traditional aur party wear ke saath kaafi stylish lagte hain! "
                "Aapko yeh alternative drop designs kaise lage?"
            )
        return {
            "status": "success",
            "reply": jhumki_reply,
            "product": chosen_first,
            "products": chosen_drops,
            "image_url": first_img,
            "model": "jhumki-alternative-playbook"
        }

    # Only intercept occasion/use-case if no specific jewellery category or design request is mentioned
    has_specific_category = any(re.search(pat, q_clean, re.I) for pats in JEWELRY_CATEGORY_CANONICAL.values() for pat in pats)

    if not has_specific_category and re.search(r"^\s*(?:daily\s*wear|office|regular|daily)\s*$", q_clean):
        daily_reply = "Samajh gayi! Daily & office wear ke liye simple, lightweight aur classy pieces sabse best rehte hain. Main aapko kuch comfortable options share karti hoon. 😊"
        return {"status": "success", "reply": daily_reply, "model": "playbook"}

    if not has_specific_category and re.search(r"^\s*(?:party|wedding|shaadi|function|heavy|occasion)\s*$", q_clean):
        party_reply = "Oh nice! Special occasions ke liye statement aur elegant designs kaafi suit karte hain. Aapko matching necklace set dekhna hai ya bracelet/earrings?"
        return {"status": "success", "reply": party_reply, "model": "playbook"}

    if not has_specific_category and re.search(r"^\s*(?:gift|gifting|kisi\s*ko\s*dena)\s*$", q_clean):
        gift_reply = "That's lovely! 😊 Kiske liye gift dekh rahe hain — sister, wife, mother ya kisi friend ke liye? Main unke taste ke according best options suggest karungi."
        return {"status": "success", "reply": gift_reply, "model": "playbook"}

    # 0d. Fast-Path for generic "friend" or "friends"
    if re.search(r"^\s*(?:dost|friend|friends|dosto|doston)\s*$", q_clean):
        friend_reply = "Aapke dost ke liye gift dekhna toh bohot achha idea hai! 😊 Kya dost male hain ya female, aur unhe kis type ki jewelry pasand aayegi (jaise Men's Kada/Bracelet, Ring ya Chain)?"
        return {"status": "success", "reply": friend_reply, "model": "playbook"}

    # 0e. Option A: Proactive Gender Qualification for Dual-Gender Categories
    # If customer asks for chains, bracelets, kadas, rings, or pendants and has NOT specified gender anywhere:
    is_asking_dual_cat = any(
        re.search(pat, q_clean, re.I)
        for cat in DUAL_GENDER_CATEGORIES
        for pat in JEWELRY_CATEGORY_CANONICAL.get(cat, [])
    )
    # Check if gender was mentioned in current query or past customer messages
    combined_convo_for_gender = f"{chat_history} {q_clean}".lower()
    has_gender_context = bool(re.search(
        r"\b(?:men|mens|male|mard|gents|boys?|husband|bhai|women|womens|ladies|ledis|ladis|ledies|girls?|female|aurat|wife|sister|didi|jhumk[ai]|jhumkhe|payal|mangalsutra|chudi|choodi|kangan|anklets?)\b|"
        r"(?:मेन्स|मेंस|जेंट्स|मर्द|लड़कों|आदमी|पुरुष|लेडीज|महिला|औरत|लड़कियों|મહિલા|લેડીઝ|મેન્સ|પુરુષ|झुमका|झुमकी|पायल|मंगलसूत्र|चूड़ी|कंगन)",
        combined_convo_for_gender
    ))

    if is_asking_dual_cat and not has_gender_context:
        # Detect language preference for natural qualification
        if re.search(r"[\u0A80-\u0AFF]", customer_query) or re.search(r"\b(?:kem\s*cho|tamne|tamare|joye)\b", customer_query, re.I):
            gender_ask = "ચોક્કસ જી! 😊 તમે જેન્ટ્સ માટે જોઈ રહ્યા છો કે લેડીઝ માટે? જેથી હું તમને એકદમ પરફેક્ટ ડિઝાઇન્સ બતાવી શકું."
        elif re.search(r"[\u0900-\u097F]", customer_query):
            gender_ask = "बिल्कुल जी! 😊 आप जेंट्स के लिए देख रहे हैं या लेडीज के लिए? ताकि मैं आपको सही और बेस्ट डिज़ाइन दिखा सकूं।"
        elif re.search(r"^[a-zA-Z0-9\s\.,!\?']+$", customer_query) and not any(bool(re.search(p, q_clean, re.I)) for p in HINDI_PATTERNS):
            gender_ask = "Sure! 😊 Are you looking for men or women? So I can share the best designs for you."
        else:
            gender_ask = "Bilkul ji! 😊 Aap gents ke liye dekh rahe hain ya ladies ke liye? Taaki main aapko perfect designs dikha sakun."
        return {"status": "success", "reply": gender_ask, "model": "proactive-qualification"}

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

    # 3. Retrieve live Shopify product context matching customer's inquiry
    product_context, top_matches = get_relevant_product_context(customer_query, chat_history)

    # Detect customer's preferred language and script dynamically
    combined_convo = f"{chat_history} {customer_query}".strip()
    
    # 1. Indic scripts detection
    if re.search(r"[\u0A80-\u0AFF]", customer_query):
        lang_pref = "Gujarati (reply in natural, polite Gujarati)"
    elif re.search(r"[\u0900-\u097F]", customer_query):
        lang_pref = "Hindi (reply in natural, polite Hindi)"
    elif re.search(r"[\u0B80-\u0BFF]", customer_query):
        lang_pref = "Tamil (reply in polite Tamil)"
    elif re.search(r"[\u0C00-\u0C7F]", customer_query):
        lang_pref = "Telugu (reply in polite Telugu)"
    elif re.search(r"[\u0C80-\u0CFF]", customer_query):
        lang_pref = "Kannada (reply in polite Kannada)"
    elif re.search(r"[\u0D00-\u0D7F]", customer_query):
        lang_pref = "Malayalam (reply in polite Malayalam)"
    elif re.search(r"[\u0980-\u09FF]", customer_query):
        lang_pref = "Bengali (reply in polite Bengali)"
    elif re.search(r"[\u0A00-\u0A7F]", customer_query):
        lang_pref = "Punjabi (reply in polite Punjabi)"
    elif re.search(r"[\u0B00-\u0B7F]", customer_query):
        lang_pref = "Odia (reply in polite Odia)"
    elif re.search(r"\b(?:kem\s*cho|majama|su\s*che|batao|karvu|tamare|tamne|shu|che|nathi|joye|chhe)\b", customer_query, re.I):
        lang_pref = "Gujarati (in Roman script / Gujlish)"
    elif re.search(r"^[a-zA-Z0-9\s\.,!\?']+$", customer_query) and not any(bool(re.search(p, combined_convo.lower(), re.I)) for p in HINDI_PATTERNS):
        lang_pref = "English (reply in warm, professional English)"
    else:
        lang_pref = "Conversational Hinglish (Hindi in Roman script)"

    prompt_parts = []
    if product_context:
        prompt_parts.append(product_context)
    if chat_history:
        prompt_parts.append(chat_history)

    prompt_parts.append(
        f"New Customer Message: {customer_query}\n"
        f"Target Language: {lang_pref}\n"
        f"CRITICAL INSTRUCTION: Reply in the customer's own language ({lang_pref}). Always speak as a woman with polite feminine grammar (e.g. 'karti hoon', 'bataungi'). DO NOT USE ANY PERSONAL NAME. Always invite/direct the customer to check out our designs on our website https://jwlbillion.com (or the specific product link). Keep it polite, concise (2-3 short sentences), reassuring Cash on Delivery is available on the website.\n"
        f"Female Stylist response:"
    )

    full_prompt = "\n\n".join(prompt_parts)

    # 4. Generate sales reply via Tiered Multi-AI Hierarchy:
    # ── Tier 1: OpenAI ChatGPT (Best sales, strict instruction following, objection handling) ──
    answer = None
    used_model = getattr(config, "OPENAI_MODEL", "gpt-4o-mini")
    openai_resp = _call_openai_api(SALES_SYSTEM_PROMPT, full_prompt)
    if openai_resp:
        answer = openai_resp
    else:
        # ── Tier 2: Primary Google Gemini (High-speed, long catalog context) ──
        logger.info("[AI Service] OpenAI unavailable or failed; failing over to Primary Gemini...")
        used_model = getattr(config, "GEMINI_MODEL", "gemini-2.5-flash")
        gemini_resp = _call_gemini_api(SALES_SYSTEM_PROMPT, full_prompt)
        if gemini_resp:
            answer = gemini_resp
        else:
            # ── Tier 3: Secondary Google Gemini Fallback Key ──
            fallback_gemini_key = getattr(config, "GEMINI_FALLBACK_API_KEY", None)
            if fallback_gemini_key:
                logger.info("[AI Service] Primary Gemini rate-limited; trying Secondary Gemini key...")
                gemini_resp_2 = _call_gemini_api(SALES_SYSTEM_PROMPT, full_prompt, api_key_override=fallback_gemini_key)
                if gemini_resp_2:
                    answer = gemini_resp_2

            # ── Tier 3b: Tertiary Google Gemini Fallback Key (3rd key) ──
            if not answer:
                fallback_gemini_key_2 = getattr(config, "GEMINI_FALLBACK_API_KEY_2", None)
                if fallback_gemini_key_2:
                    logger.info("[AI Service] Secondary Gemini rate-limited; trying 3rd Gemini key...")
                    gemini_resp_3 = _call_gemini_api(SALES_SYSTEM_PROMPT, full_prompt, api_key_override=fallback_gemini_key_2)
                    if gemini_resp_3:
                        answer = gemini_resp_3

            # ── Tier 3c: Quaternary Google Gemini Fallback Key (4th key) ──
            if not answer:
                fallback_gemini_key_3 = getattr(config, "GEMINI_FALLBACK_API_KEY_3", None)
                if fallback_gemini_key_3:
                    logger.info("[AI Service] 3rd Gemini rate-limited; trying 4th Gemini key...")
                    gemini_resp_4 = _call_gemini_api(SALES_SYSTEM_PROMPT, full_prompt, api_key_override=fallback_gemini_key_3)
                    if gemini_resp_4:
                        answer = gemini_resp_4

            # ── Tier 3d: Quinary Google Gemini Fallback Key (5th key) ──
            if not answer:
                fallback_gemini_key_4 = getattr(config, "GEMINI_FALLBACK_API_KEY_4", None)
                if fallback_gemini_key_4:
                    logger.info("[AI Service] 4th Gemini rate-limited; trying 5th Gemini key...")
                    gemini_resp_5 = _call_gemini_api(SALES_SYSTEM_PROMPT, full_prompt, api_key_override=fallback_gemini_key_4)
                    if gemini_resp_5:
                        answer = gemini_resp_5

    if not answer:
        # ── Tier 4: Groq High-Speed LPU Failover (0.2s sub-second response) ──
        logger.info("[AI Service] OpenAI and Gemini unavailable; failing over to Groq LPU...")
        groq_resp = _call_groq_api(SALES_SYSTEM_PROMPT, full_prompt)
        if groq_resp:
            answer = groq_resp
            used_model = getattr(config, "GROQ_MODEL", "qwen/qwen3.8-27b")

    if not answer:
        return {
            "status": "error",
            "error": "All AI inference engines failed",
            "reply": None,
            "model": used_model
        }

    try:
        # Clean any leftover meta tags or artifacts if present
        answer = re.sub(r"^(?:Riya|Maya|Consultant|JWL Stylist):\s*", "", answer, flags=re.I).strip()
        
        # Clean markdown link syntax: WhatsApp does not support markdown links like [here](https://...)
        # Convert [text](url) -> url so WhatsApp displays a clean, clickable preview link
        answer = re.sub(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)', r'\2', answer)
        # Also clean broken markdown patterns like [Product Link](https://...) or [text]\s*\((https?://...)\)
        answer = re.sub(r'\[[^\]]*\]\s*\(?(https?://[^\s\)]+)\)?', r'\1', answer)

        # If LLM outputted literal placeholder like [Link], [here], [view] instead of the actual URL
        if top_matches and re.search(r'\[(?:Link|here|view|details?|product|website|Product Link)\]', answer, re.I):
            primary_url = top_matches[0].get("product_url") or top_matches[0].get("shop_url") or "https://jwlbillion.com"
            answer = re.sub(r'\[(?:Link|here|view|details?|product|website|Product Link)\]', primary_url, answer, flags=re.I)

        # Clean any accidental Karat references (18K, 22K, 24K, karat, carat)
        answer = re.sub(r'\b(?:18\s*k(?:arat)?|22\s*k(?:arat)?|24\s*k(?:arat)?)\b', 'premium', answer, flags=re.I)
        answer = re.sub(r'\b(?:karats?|carats?)\b', '', answer, flags=re.I)

        # STRICT URL & RECOMMENDATION VALIDATION (ZERO HALLUCINATION GATE):
        # 1. Fetch live published Shopify catalog handles to strictly verify existence
        live_catalog_data = fetch_shopify_products(limit=250)
        live_catalog_products = live_catalog_data.get("products", [])
        live_catalog_handles = {p.get("handle") for p in live_catalog_products if p.get("handle")}
        valid_urls = {m.get("product_url") for m in top_matches if m.get("product_url")}
        primary_verified_url = top_matches[0].get("product_url") if top_matches else "https://jwlbillion.com"

        # Helper to check if any extracted link is an authentic live Shopify product or collection
        def sanitize_any_store_link(match):
            u = match.group(0).rstrip(".,;:!?")
            # If it's a specific product URL: check against verified live handles
            prod_match = re.search(r'/products/([a-zA-Z0-9_-]+)', u)
            if prod_match:
                slug = prod_match.group(1).lower()
                if slug in live_catalog_handles:
                    return f"https://jwlbillion.com/products/{slug}"
                # If not live in catalog, replace with top verified match or collection
                return primary_verified_url

            # If it's a collection URL: check if it's a known valid collection
            coll_match = re.search(r'/collections/([a-zA-Z0-9_-]+)', u)
            if coll_match:
                cslug = coll_match.group(1).lower()
                if cslug in ["bangle", "chains", "jewelry-set", "womens-jewelers-set", "womens-earrings", "anklet", "all", "mens-collection"]:
                    return f"https://jwlbillion.com/collections/{cslug}"
                elif cslug in ["necklace", "necklaces", "pendant", "pendants"]:
                    return "https://jwlbillion.com/collections/jewelry-set"
                elif cslug in ["earring", "earrings"]:
                    return "https://jwlbillion.com/collections/womens-earrings"
                elif cslug in ["bracelet", "bracelets", "kada", "kadas"]:
                    return "https://jwlbillion.com/collections/bangle"
                return "https://jwlbillion.com/collections/all"

            # Fallback for weird URLs like /ladies-earrings/... or hallucinated routes
            if u.startswith("https://jwlbillion.com"):
                # Check if it was trying to point to an earring, bangle, chain, ring, etc.
                u_lower = u.lower()
                if "earring" in u_lower:
                    return "https://jwlbillion.com/collections/womens-earrings"
                elif "bangle" in u_lower:
                    return "https://jwlbillion.com/collections/bangle"
                elif "bracelet" in u_lower or "kada" in u_lower:
                    return "https://jwlbillion.com/collections/bangle"
                elif "chain" in u_lower:
                    return "https://jwlbillion.com/collections/chains"
                elif "ring" in u_lower:
                    return "https://jwlbillion.com/collections/womens-ring"
                elif "necklace" in u_lower or "pendant" in u_lower or "gale" in u_lower:
                    return "https://jwlbillion.com/collections/jewelry-set"
                return primary_verified_url
            return u

        # Replace all store URLs with verified live URLs
        answer = re.sub(r'https?://(?:www\.)?jwlbillion\.com[^\s\)\],]+', sanitize_any_store_link, answer)

        # If LLM generated a product link or pitched a product without verified top_matches,
        # replace with a safe clarification asking the customer what they want, rather than hallucinating!
        if not top_matches and (re.search(r'https?://jwlbillion\.com/products/[^\s\)\],]+', answer) or re.search(r'https?://jwlbillion\.com/collections/[^\s\)\],]+', answer)):
            logger.warning("[AI Service] Blocked hallucinated product recommendation with no live match.")
            answer = (
                "Hamare paas wedding aur party wear ke liye bohot hi sundar gale ke necklaces aur pendant sets uplabdh hain! ✨\n\n"
                "Aap ladies ke liye dekh rahi hain ya men ke liye? Aap hamari official website https://jwlbillion.com par saare trending designs aur videos bhi aaram se dekh sakti hain."
            )

        # Prevent weird halucinated repetitive names or phrases like "Keya, " at the start
        answer = re.sub(r'^(?:Keya|Kya),?\s*', '', answer, flags=re.I).strip()

        # Clean broken Hindi grammar patterns generated by small LLMs
        answer = re.sub(r'\b(?:kripya\s*kijiye|kripya\s*kijiye\s*ji),?\s*', 'Most welcome ji! ', answer, flags=re.I)
        answer = re.sub(r'\bkripya\b', '', answer, flags=re.I)
        answer = re.sub(r'\b(?:apna\s*aap|apne\s*aap),?\s*', '', answer, flags=re.I)
        answer = re.sub(r'\bhai\s+ya\s+₹', 'iska price ₹', answer, flags=re.I)
        answer = re.sub(r'\blikha\s+chahiye\b', 'dekhna chahenge', answer, flags=re.I)
        answer = re.sub(r'\blikha\b', 'dekhna', answer, flags=re.I)
        answer = re.sub(r'\bkarenga\b', 'karenge', answer, flags=re.I)
        answer = re.sub(r'\bdekhna\s+pasand\s+kareng[ae]\b', 'dekhna chahenge', answer, flags=re.I)
        answer = re.sub(r'\bpasand\s+karenga\b', 'pasand karenge', answer, flags=re.I)
        answer = re.sub(r'\bchahe\?', 'chahenge?', answer, flags=re.I)
        # Remove repeated customer phrases like "bhej dijiye" erroneously appended to product titles
        answer = re.sub(r'\b(?:bhej\s*dijiye|bhej\s*do|dikha\s*dijiye|dikha\s*do)\.?', '', answer, flags=re.I).strip()
        answer = re.sub(r'\s{2,}', ' ', answer).strip()

        # Determine products and images to send:
        # Collect all products that were actively mentioned, linked, or pitched in the AI's reply
        recommended_products = []
        for p in top_matches:
            p_title = (p.get("title") or "").strip()
            p_url = (p.get("product_url") or "").rstrip(".,;:!?")
            # 1. Match by URL in answer
            if p_url and p_url in answer:
                recommended_products.append(p)
            # 2. Match by full title in answer
            elif p_title and p_title.lower() in answer.lower():
                recommended_products.append(p)
            else:
                # 3. Match by major title keywords (handles bolding like *Golden Grace...*)
                title_words = [w.lower() for w in re.split(r'[^a-zA-Z0-9]+', p_title) if len(w) > 3]
                if title_words and sum(1 for w in title_words if w in answer.lower()) >= min(3, len(title_words)):
                    recommended_products.append(p)

        # If none matched by explicit string but top_matches exist and AI offered products
        if not recommended_products and top_matches:
            recommended_products = top_matches[:2]

        # Keep unique products up to 3
        seen_p_ids = set()
        unique_rec_prods = []
        for p in recommended_products:
            p_id = p.get("id") or p.get("product_url")
            if p_id and p_id not in seen_p_ids:
                seen_p_ids.add(p_id)
                unique_rec_prods.append(p)

        first_prod = unique_rec_prods[0] if unique_rec_prods else (top_matches[0] if top_matches else None)
        first_img = _clean_product_photo(first_prod) if first_prod else None

        return {
            "status": "success",
            "reply": answer,
            "image_url": first_img,
            "product": first_prod,
            "products": unique_rec_prods,
            "model": used_model
        }
    except Exception as e:
        logger.error(f"[AI Service] Post-processing reply failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "reply": None,
            "model": used_model
        }
