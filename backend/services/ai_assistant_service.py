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
            "wa0060", "wa0007", "wa0012", "wa0013", "wa0018"
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

SALES_SYSTEM_PROMPT = """You are Riya, a warm, polite female jewelry stylist for JWL Billion (jwlbillion.com).
JWL Billion crafts premium 18K/24K gold-plated, silver-finish, American Diamond / CZ jewelry (₹300–₹2,000).

CORE CONVERSATION RULES:
1. STRICT FEMALE PERSONA & NATURAL HINGLISH WITH RESPECTFUL "AAP":
   - Your name is Riya. If asked your name, introduce yourself as Riya from JWL Billion.
   - Always speak as a female/girl using feminine Hindi grammar (e.g., 'main suggest karungi', 'bata sakti hoon', 'main check karti hoon', 'dekh sakti hoon'). NEVER use masculine verbs like 'karunga', 'bataunga'.
   - Speak ONLY in natural, fluent Romanized Hinglish (Hindi written in English alphabet).
   - EXCELLENT EXAMPLES:
     * "Haan ji, bilkul! Yeh dekhiye hamara sundar [Product Title] (₹450): https://jwlbillion.com/products/link . Yeh daily wear aur party wear dono ke liye perfect hai! Aapko kaisa laga?"
     * "Hamare paas bohot pyaare designs hain! Aapko simple aur subtle design pasand hai ya thoda trendy aur stylish?"
   - FORBIDDEN GRAMMAR:
     * NEVER repeat customer request phrases like "bhej dijiye", "dikha do", or "bhejo".
     * NEVER say "Apna aap" or "Apne aap".
     * NEVER say "hai ya ₹270" or "X hai ya ₹Y". Say "iska price ₹Y hai" or "(₹Y)".
     * NEVER say "likha" or "karenga" or "pasand karenga". Say "Aap dekhna chahenge?" or "Aapko kaisa design pasand hai?".
   - NEVER write in pure English sentences. NEVER write in Devanagari script.
   - Always use respectful "Aap" (never use tu/tum).
2. PRODUCT RECOMMENDATION & REAL LINK RULE (CRITICAL):
   - When suggesting a product, ONLY recommend items listed under "Available Live Store Products".
   - ALWAYS mention its exact title, price, and output the EXACT FULL link provided under "Available Live Store Products" (e.g. https://jwlbillion.com/products/... ).
   - NEVER invent or hallucinate product names or URLs that are not in the provided live store context.
   - If NO products are listed in "Available Live Store Products", DO NOT make up fake products or links. Instead, warmly ask what specific item or category they would prefer.
   - NEVER write placeholder tags like '[Link]', '[Product Link]', '[here]', or markdown links like [text](url).
   - Only recommend 1 matching product at a time.
3. FORMULA: Listen -> React -> Recommend 1 Item with Link -> Ask 1 simple styling question.
4. MID-RANGE FIRST STRATEGY (CRITICAL):
   - Always showcase our premium mid-range bestseller designs (₹500–₹1,200) first to make a strong premium impression.
   - Do NOT pitch cheap or entry-level items (< ₹400) first unless the customer explicitly asks for lowest price or low budget.
5. PRICE DISCLOSURE: If asked "Price?", give the exact ₹ price immediately!

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
            sender = "Customer" if m.sender_type == "CUSTOMER" else "Riya (JWL Stylist)"
            body = (m.text or "").strip()
            if body and not body.startswith("Sent interactive"):
                history_lines.append(f"{sender}: {body}")
        
        return "\n".join(history_lines)
    except Exception as e:
        logger.warning(f"[AI Service] Error loading chat history: {e}")
        return ""


JEWELRY_CATEGORY_CANONICAL = {
    "bracelet": [r"\b(?:bracelets?|bracelete?|breslets?|breslete?|braclets?|wristlets?|kadas?|kade|kara|cuff)\b", r"ब्रेसलेट|कड़ा"],
    "bangle": [r"\b(?:bangles?|banglez|chudi|choodi|choodiyan|chudiya|kangan|bangals?|bangels?)\b", r"चूड़ी|कंगन"],
    "anklet": [r"\b(?:anklets?|payals?|pajeb|panjeb|pair\s*ke)\b", r"पायल|पाजेब|एंक्लेट"],
    "ring": [r"\b(?:rings?|ringss?|anguthi|anguthiyan|anguti|chhalla)\b", r"अंगूठी|रिंग"],
    "chain": [r"\b(?:chains?|chane|chaines?|chen|chene|cene|chainke|chenke|chainka)\b", r"चैन|चेन"],
    "necklace": [r"\b(?:necklaces?|necjlace?|haar|haars?|choker|mangalsutra|pendant|pendants?|pendent)\b", r"हार|नेकलेस|पेंडेंट"],
    "earring": [r"\b(?:earrings?|ear\s*rings?|jhumk[ai]|balis?|studs?|ear?nings?|e?rings?|erring|earings?|ering|earng)\b", r"झुमका|बाली|इयररिंग"]
}


def get_relevant_product_context(customer_query: str, chat_history: str = "") -> tuple[str, list[dict]]:
    """Finds matching live Shopify products based on query and customer conversation history."""
    try:
        data = fetch_shopify_products(limit=150)
        products = data.get("products", [])
        if not products:
            return "", []

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

        # 2. Gender detection with negation awareness (e.g. "ladies nahi chaiyea" -> is_men=True, is_women=False)
        combined_customer_text = f"{customer_history_text} {q_lower}".strip()

        # Check for explicit negation of women/ladies
        women_negated = bool(re.search(
            r"\b(?:ladies|women|aurat|ladki|girls?)\s*(?:nahi|not|mat|no|dont|don't|chahiye\s*nahi)\b|"
            r"\b(?:nahi|not|no|dont|don't)\s*(?:chahiye\s*)?(?:ladies|women|aurat|girls?)\b",
            combined_customer_text
        ))
        men_negated = bool(re.search(
            r"\b(?:men|mens|gents|mard|boys?)\s*(?:nahi|not|mat|no|dont|don't|chahiye\s*nahi)\b|"
            r"\b(?:nahi|not|no|dont|don't)\s*(?:chahiye\s*)?(?:men|mens|gents)\b",
            combined_customer_text
        ))

        is_men = bool(re.search(r"\b(?:men|mens|male|mard|gents|boys?|husband|bhai)\b", combined_customer_text)) and not men_negated
        is_women = bool(re.search(r"\b(?:women|womens|ladies|ledis|ladis|ledies|girls?|female|aurat|wife|sister|didi)\b", combined_customer_text)) and not women_negated

        # If ladies/women was explicitly negated, reinforce men
        if women_negated:
            is_women = False
            is_men = True

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

        valid_matches.sort(key=product_rank, reverse=True)
        top_matches = [m[1] for m in valid_matches[:2]]

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
            "maxOutputTokens": 300
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
        "max_tokens": 250,
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


def transcribe_voice_with_sarvam(audio_file_path: str) -> Optional[str]:
    """
    Transcribes WhatsApp audio/voice notes using Sarvam AI's Saaras Indic ASR model.
    Handles Indian accents, Hindi, Gujarati, Marathi, and Hinglish voice notes.
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
        data = {"model": "saaras:v2", "mode": "transcribe"}

        with open(audio_file_path, "rb") as f:
            files = {"file": (os.path.basename(audio_file_path), f, "audio/ogg")}
            resp = requests.post(url, headers=headers, data=data, files=files, timeout=15)
            if resp.status_code == 200:
                transcript = resp.json().get("transcript", "").strip()
                logger.info(f"[Sarvam ASR] Transcribed voice note: {transcript}")
                return transcript
            else:
                logger.warning(f"[Sarvam ASR] Failed ({resp.status_code}): {resp.text}")
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
        "max_tokens": 200,
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

    # 00. Guard against single characters, typos, or gibberish (e.g. "H", "k", "??", "...")
    # Don't dump products or assume intent — politely ask customer to clarify
    if len(q_clean) <= 2 and not re.match(r"^(?:hi|ok|hm|no|ji)$", q_clean):
        clarify_short = "Ji, kahiye! 😊 Aap kis type ki jewellery dekh rahe hain — jaise Earrings, Necklace, Rings ya Bracelets?"
        return {"status": "success", "reply": clarify_short, "model": "playbook"}

    # 0a. Instant Fast-Path for Meta Ads Default Inbound ("Hello! Can I get more info on this?")
    if re.search(r"^(?:hello!?\s*)?can\s*i\s*get\s*more\s*info\s*(?:on\s*this)?\??$", q_clean):
        welcome_hinglish = (
            "Hey! Welcome to JWL Billion 😊\n\n"
            "Thanks for checking out our collection!\n\n"
            "Aap kuch specific jewellery dekh rahe hain ya bas collection explore kar rahe hain?"
        )
        return {"status": "success", "reply": welcome_hinglish, "model": "qwen2.5:1.5b"}

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

    # 0c. Fast-Path for Acknowledgements, Sign-offs & Thank Yous ("ok thanks", "thank you", "dhanyawad", "koi nahi")
    if re.search(r"^\s*(?:ok\s*)?(?:thanks?|thank\s*you|shukriya|dhanyawad|welcome|ok\s*bye|bye|good\s*night|alvida|tc|take\s*care)\s*!*\s*$", q_clean):
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
        gift_reply = "That's lovely! 😊 Kiske liye gift dekh rahe hain — sister, wife, mother ya kisi friend ke liye? Main unke taste ke according best options suggest karungi."
        return {"status": "success", "reply": gift_reply, "model": "playbook"}

    # 0d. Fast-Path for generic "friend" or "friends"
    if re.search(r"^\s*(?:dost|friend|friends|dosto|doston)\s*$", q_clean):
        friend_reply = "Aapke dost ke liye gift dekhna toh bohot achha idea hai! 😊 Kya dost male hain ya female, aur unhe kis type ki jewelry pasand aayegi (jaise Men's Kada/Bracelet, Ring ya Chain)?"
        return {"status": "success", "reply": friend_reply, "model": "playbook"}

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
        f"CRITICAL INSTRUCTION: Reply in warm, natural Hindi / Hinglish with respectful 'Aap'. Always speak as a female stylist named Riya using feminine grammar ('main suggest karungi', 'bata sakti hoon'). Be precise, helpful, and concise (2 short sentences).\n"
        f"Riya (Female JWL Stylist response, concise, friendly, selling with links/prices if product was asked):"
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

        # STRICT URL VALIDATION: Prevent 404 links caused by LLM hallucinating product slugs.
        # Ensure any product link in the text is strictly replaced with a verified product_url from live Shopify data.
        # If no verified product matches exist in context, strip the hallucinated link entirely instead of falling back to collections/all!
        primary_verified_url = top_matches[0].get("product_url") if top_matches else None
        valid_urls = {m.get("product_url") for m in top_matches if m.get("product_url")}
        def sanitize_product_link(match):
            u = match.group(0).rstrip(".,;:!?")
            if u not in valid_urls:
                return primary_verified_url or ""
            return u
        answer = re.sub(r'https?://jwlbillion\.com/products/[^\s\)\],]+', sanitize_product_link, answer)

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

        # Determine whether to accompany this reply with a product image
        # Whenever a product from Shopify is actively recommended or presented, attach its image
        send_image_url = None
        if top_matches:
            first_match = top_matches[0]
            img_candidate = _clean_product_photo(first_match)
            if img_candidate:
                # Attach photo if the AI referenced the product, mentioned price, provided link, or recommended it
                has_product_ref = (
                    "https://" in answer or
                    "₹" in answer or
                    "dekhiye" in answer.lower() or
                    first_match.get("title", "").lower() in answer.lower()
                )
                if has_product_ref:
                    send_image_url = img_candidate

        return {
            "status": "success",
            "reply": answer,
            "image_url": send_image_url,
            "product": top_matches[0] if top_matches else None,
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
