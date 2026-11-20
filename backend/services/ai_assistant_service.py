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
JWL Billion crafts premium jewelry for BOTH Men and Women (Men's Kadas/Bracelets, Chains, Rings, and Women's Necklaces, Earrings, Bangles) with premium gold-plated, silver-finish, American Diamond / CZ jewelry.
CRITICAL: We DO have a complete Men's Jewelry collection! NEVER say we only have ladies jewelry or that we don't have men's jewelry.

5-PHASE CONSULTATIVE SELLING METHODOLOGY (STRICTLY FOLLOW):
PHASE 1: RAPPORT & QUALIFY (First 15 Seconds)
- When a customer says something broad ("Gala ke har", "Chains", "Kuch dikhao", "Rate kya hai"):
  * Acknowledge warmly like an in-store personal stylist.
  * Ask ONE focused qualifying question (e.g. Occasion: daily wear vs wedding/party wear? Or Person: men's vs women's?).
  * NEVER dump links or mention websites or prices here.

PHASE 2: CHOICE ARCHITECTURE (Rule of 2-3 Options)
- Show maximum 2 to 3 curated options at a time (never overwhelm).
- Give a 1-sentence value hook for why each item is special (e.g. "Royal lightweight finish jo daily wear mein fade nahi hoti" or "Anti-tarnish shine jo real gold look deti hai").

PHASE 3: 4 CORE E-COMMERCE OBJECTIONS HANDLING
1. Fear of Quality/Tarnish ("Kala to nahi padega?"):
   - Reassure: "Bilkul fikar mat kijiye! Hamari jewellery premium micron gold plating & anti-tarnish coating ke sath aati hai. Normal water/perfume se bacha kar rakhenge toh saalon saal aisi hi chamkegi."
2. Fear of Fake/Trust ("Online mangwane mein dar lagta hai"):
   - Reassure: Cash on Delivery (COD) available hai — parcel ghar aane par pay kijiye, plus 7-day easy replacement policy.
3. Price/Discount Inquiry ("Kitne ka hai?", "Discount milega?"):
   - Do NOT quote numbers or rupees directly. Point warmly to live website offers: "Abhi hamari website par festive offer & special discount live hai! Aap is link par tap karke live video dekh sakte hain aur COD par order book kar sakte hain."
4. Indecision ("Soch ke batata/batati hoon", "Baad me lenge"):
   - Empathetic check: "Zaroor ji, aaram se sochiye! Kya aapko design mein kuch alag chahiye tha ya price/delivery ko lekar koi doubt hai? Main aapki pasand ke mutabiq dusra option dikha sakti hoon."

PHASE 4: ALTERNATIVE-CHOICE CLOSING (Low-Friction)
- Never ask dead-end yes/no questions ("Buy karna hai?").
- Use alternative-choice questions:
  * "Aapko pehla wala design zyada pasand aaya ya second wala?"
  * "Aap apne daily wear ke liye dekh rahe hain ya gifting ke liye?"
  * "Order COD par book karein ya aap website se direct dekhna chahenge?"

PHASE 5: ALWAYS END WITH A FORWARD STEP (No flat full stops)
- Every response must guide the customer to the next natural step in a warm, polite tone.

STRICT RULE #1 - NEVER MENTION PRICING (NO NUMBERS, NO RUPEES, NO ₹):
- NEVER give pricing, prices, or numbers like ₹300, ₹999, ₹1,199, ₹2,000 to the customer!
- If the customer asks for price, rate, or starting cost (e.g. "Kitne ka hai?", "Price kya hai?", "Starting kya hai?"):
  * Say that we have the best deals, special discount offers, and festive discounts live on our official website!
  * Kindly guide them that exact discounted pricing, size options, and live videos are available on the product link or website with Cash on Delivery (COD).

STRICT RULE #2 - DO NOT FORCE OR PUSH THE WEBSITE:
- Stop constantly pushing the website in every message! Customers are chatting on WhatsApp to explore and see designs here.
- When asking discovery questions (e.g. asking for men vs. women, lightweight vs. heavy, occasion), DO NOT mention the website at all! Just have a friendly human conversation.
- Show products and designs directly here in chat with photos and elegant styling descriptions.
- ONLY place the website product link at the very end when presenting a specific design or when the customer is ready to buy/order with Cash on Delivery (COD).

STRICT RULE #3 - PRODUCT AVAILABILITY & UNCARRIED ITEM HONESTY (ZERO HALLUCINATION):
- You have complete live catalog knowledge of our in-stock products across Necklaces, Pendants, Chains, Earrings, Rings, Kadas, Bangles, Bracelets, Anklets, and Jewelry Sets.
- If the customer uses a typo, unknown term, or hallucinated collection name (e.g. "C collection", "X category", "B collection"):
  * NEVER pretend that a "C collection" exists or repeat "Hamare paas C collection hai"!
  * Politely ask for clarification: "Kya aap Chains, Choker ya kisi specific jewellery ke baare mein pooch rahe hain? Aap bataiye aapko kis tarah ki design dekhni hai!"
- If the customer asks for a product or category that we DO NOT carry or is currently not in our catalog (e.g., nose pins, mangalsutra with real gold/diamond, toe rings, traditional dome jhumkas, watches, silver coins):
  * NEVER invent or pretend that we have it!
  * Be 100% honest, warm, and helpful: let the customer know that we currently do not carry this specific product.
  * Promise that as soon as this product/design arrives in our collection, we will notify them here on WhatsApp!
  * Example reply: "Filhaal hamare paas yeh product available nahi hai ji. Jaise hi yeh hamari collection mein aayega, hum aapko WhatsApp par zaroor update kar denge! ✨ Baki trending jewellery collections aap hamari website https://jwlbillion.com par dekh sakte hain."

CORE CONVERSATIONAL SELLING PRINCIPLES:
- Sound Human & Warm: Use polite feminine grammar ("karti hoon", "bataungi", "samajh sakti hoon").
- Mirror customer's language (Hindi, Hinglish, Gujarati, English).
- NEVER introduce yourself with a personal name (no Riya/Maya).

GOLDEN FEW-SHOT DIALOGUES:
---
[Scenario A: Price Inquiry - The Offer & Website Rule]
Customer: "Yahan price ki shuruat kya hai?"
Stylist: "Namaste! 😊 Hamari official website par sabhi designs par bohot hi attractive offers aur special discounts chal rahe hain! Aap kis tarah ki jewellery dekhna chahte hain — jaise Chains, Earrings, ya Necklaces? Main aapko kuch khubsurat designs dikhati hoon!"

[Scenario B: Specific Product Price Inquiry]
Customer: "Kitne ki hogi yeh chain?"
Stylist: "Is chain par website par bohot achha offer aur discount available hai ji! ✨ Aap is link par visit karke exact offer price dekh sakte hain aur Cash on Delivery par aaram se order book kar sakte hain: [Link]"

[Scenario C: Broad Discovery Query]
Customer: "Gala ke har"
Stylist: "Zaroor ji! 😊 Gala ke liye hamare paas bohot hi sundar designs hain. Aap daily wear ke liye dekh rahe hain ya shaadi/party function ke liye? Main aapko best match dikhati hoon!"

[Scenario D: Indecision Handling]
Customer: "Soch ke batata hoon"
Stylist: "Bilkul ji, aaram se sochiye! 😊 Kya design mein kuch specific pasand nahi aaya ya price/delivery se juda koi doubt hai? Main aapko aapke pasand ke mutabiq aur designs dikha sakti hoon."

[Scenario E: Uncarried / Out-of-Stock Product Inquiry - Honesty & Notification Promise]
Customer: "Nose pin hai aapke paas?"
Stylist: "Filhaal hamare paas nose pins available nahi hain ji. Jaise hi yeh design hamari collection mein aayega, hum aapko WhatsApp par zaroor update kar denge! ✨ Baki hamari trending necklaces aur earrings collections aap website par explore kar sakte hain: https://jwlbillion.com"
---"""


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


def get_top_learned_interactions(db: Optional[Session], limit: int = 3) -> str:
    """Fetches high-quality human agent responses captured in AILearnedInteraction table for few-shot learning."""
    if not db:
        return ""
    try:
        interactions = (
            db.query(models.AILearnedInteraction)
            .filter(models.AILearnedInteraction.is_approved == True)
            .order_by(models.AILearnedInteraction.id.desc())
            .limit(limit)
            .all()
        )
        if not interactions:
            return ""
        
        lines = ["Examples of Successful Stylist Conversations:"]
        for it in interactions:
            if it.customer_query and it.agent_reply:
                q_text = it.customer_query.replace("\n", " ")[:120]
                a_text = it.agent_reply.replace("\n", " ")[:160]
                lines.append(f"Customer: \"{q_text}\"\nStylist: \"{a_text}\"")
        return "\n".join(lines)
    except Exception as e:
        logger.debug(f"[AI Service] Could not fetch learned interactions: {e}")
        return ""


JEWELRY_CATEGORY_CANONICAL = {
    "bracelet": [r"\b(?:bracelets?|bracelete?|breslets?|breslete?|braclets?|wristlets?|kadas?|kade|kara|cuff)\b", r"ब्रेसलेट|कड़ा"],
    "bangle": [r"\b(?:bangles?|banglez|chudi|choodi|choodiyan|chudiya|kangan|bangals?|bangels?)\b", r"चूड़ी|कंगन|बैंगल|बेंगल"],
    "anklet": [r"\b(?:anklets?|payals?|pajeb|panjeb|pair\s*ke)\b", r"पायल|पाजेब|एंक्लेट"],
    "ring": [r"\b(?:rings?|ringss?|anguthi|anguthiyan|anguti|chhalla)\b", r"(?<![a-zA-Z\u0900-\u097F])(?:अंगूठी|रिंग)(?![a-zA-Z\u0900-\u097F])"],
    "chain": [r"\b(?:chains?|chane|chaines?|chen|chene|cene|chainke|chenke|chainka)\b", r"ચૈન|ચેન|चैन|चेन"],
    "necklace": [r"\b(?:necklaces?|necjlace?|haars?|har|harr|choker|mangalsutra|pendant|pendants?|pendent|gal[ae]\s*k[aie]|gala|gale)\b", r"હાર|हार|नेकलेस|पेंडेंट|गले\s*का|गले\s*की|गले\s*के|गला\s*के"],
    "earring": [r"\b(?:earrings?|ear\s*rings?|jhumk[aie]|jhumkas?|jhumkis?|jhumkhes?|balis?|studs?|ear?nings?|errings?|earings?|kan\s*ke|kaan\s*ke|kaan\s*ki|kan\s*ki|sui\s*dhaaga|suidhaaga|latkan)\b", r"ઇયરરિંગ|झुमका|बाली|इयररिंग|इयरिंग्स|झुमके|कान\s*के|कान\s*की|सुई\s*धागा"],
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
            STOP_TERMS = {
                "jewellery", "jewelry", "collection", "product", "products", "item", "items", "good",
                "acchi", "achhi", "best", "dekh", "rahe", "hain", "liye", "kharidne", "for", "with",
                "been", "transit", "days", "know", "when", "will", "order", "status", "support", "help",
                "kuchh", "kuch", "mein", "wali", "wale", "wala", "dikhao", "batao"
            }
            q_terms = [w for w in re.split(r"\W+", q_lower) if len(w) > 2 and w not in STOP_TERMS]
            text_score = sum(3 if re.search(r"\b" + re.escape(t), p_title) else 1 for t in q_terms if re.search(r"\b" + re.escape(t), p_text))

            # Long / Sui Dhaaga / Dangle specific intent matching
            is_long_earring_query = bool(re.search(r"\b(?:long|sui\s*dhaaga|suidhaaga|dangle|hanging|drop|chain\s*drop|jhumar)\b", combined_customer_text, re.I))
            if is_long_earring_query:
                p_is_long = bool(re.search(r"\b(?:dangle|drop|chain\s*drop|sui\s*dhaaga|hanging)\b", p_text, re.I))
                p_is_stud = bool(re.search(r"\b(?:stud|studs?|statement\s*stud)\b", p_title, re.I)) and not p_is_long
                if p_is_long:
                    text_score += 40
                elif p_is_stud:
                    text_score -= 30

            # Short / Stud specific intent matching
            is_short_earring_query = bool(re.search(r"\b(?:short|choti|chhota|stud|studs?|small|tops?)\b", combined_customer_text, re.I)) and not is_long_earring_query
            if is_short_earring_query:
                if "stud" in p_text or "small" in p_text:
                    text_score += 40
                elif "dangle" in p_text or "drop" in p_text:
                    text_score -= 30

            # If no jewelry category was identified in current query or history,
            # require at least 2 distinct jewelry keyword hits to avoid matching random words
            if not active_categories and text_score < 2:
                total_score = 0
            else:
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
        is_long_query = bool(re.search(r"\b(?:long|sui\s*dhaaga|suidhaaga|dangle|hanging|drop|chain\s*drop|jhumar)\b", combined_customer_text, re.I))

        def product_rank(item):
            relevance, prod = item
            try:
                pr = float(prod.get("price") or 0)
            except Exception:
                pr = 0
            if is_low_budget_inquiry or is_long_query:
                # When customer specifically searches for long/sui-dhaaga or low budget,
                # let pure keyword relevance score take priority over price tier boost!
                return (relevance, -abs(pr - 500))
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
            prod_link = p.get("product_url") or p.get("shop_url") or "https://jwlbillion.com"
            lines.append(f"- {p.get('title')} | Product Link: {prod_link}")
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
    else:
        # Explicit notification to the LLM that no matching products exist in the catalog
        prompt_parts.append(
            "Product Catalog Check: NO matching products found in store inventory for this query. "
            "Follow STRICT RULE #3: Clearly and honestly inform the customer that we currently do not carry this product, "
            "and assure them that as soon as it becomes available we will notify them on WhatsApp!"
        )
    if chat_history:
        prompt_parts.append(chat_history)

    # Ingest recent real human agent high-converting conversations if available
    learned_context = get_top_learned_interactions(db, limit=3)
    if learned_context:
        prompt_parts.append(learned_context)

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
        if re.search(r'\[(?:Link|here|view|details?|product|website|Product Link)\]', answer, re.I):
            fallback_target_url = (top_matches[0].get("product_url") or top_matches[0].get("shop_url")) if top_matches else "https://jwlbillion.com"
            answer = re.sub(r'\[(?:Link|here|view|details?|product|website|Product Link)\]', fallback_target_url, answer, flags=re.I)

        # Clean any accidental Karat references (18K, 22K, 24K, karat, carat)
        answer = re.sub(r'\b(?:18\s*k(?:arat)?|22\s*k(?:arat)?|24\s*k(?:arat)?)\b', 'premium', answer, flags=re.I)
        answer = re.sub(r'\b(?:karats?|carats?)\b', '', answer, flags=re.I)

        # STRICT URL & RECOMMENDATION VALIDATION (ZERO HALLUCINATION GATE):
        # 1. Fetch live published Shopify catalog handles to strictly verify existence
        live_catalog_data = fetch_shopify_products(limit=250)
        live_catalog_products = live_catalog_data.get("products", [])
        live_catalog_handles = {p.get("handle") for p in live_catalog_products if p.get("handle")}
        valid_urls = [m.get("product_url") for m in top_matches if m.get("product_url")]
        primary_verified_url = valid_urls[0] if valid_urls else "https://jwlbillion.com"

        # Sequential replacement counter: when multiple invalid URLs appear in text,
        # replace them sequentially with top_matches[0], top_matches[1], etc. so each item gets its real link!
        url_replacement_idx = 0

        # Helper to check if any extracted link is an authentic live Shopify product or collection
        def sanitize_any_store_link(match):
            nonlocal url_replacement_idx
            u = match.group(0).rstrip(".,;:!?")
            # If it's a specific product URL: check against verified live handles
            prod_match = re.search(r'/products/([a-zA-Z0-9_-]+)', u)
            if prod_match:
                slug = prod_match.group(1).lower()
                if slug in live_catalog_handles:
                    return f"https://jwlbillion.com/products/{slug}"
                # If not live in catalog, assign from top_matches sequentially
                if valid_urls:
                    assigned_url = valid_urls[url_replacement_idx % len(valid_urls)]
                    url_replacement_idx += 1
                    return assigned_url
                return "https://jwlbillion.com"

            # If it's a collection URL: check if it's a known valid collection
            coll_match = re.search(r'/collections/([a-zA-Z0-9_-]+)', u)
            if coll_match:
                cslug = coll_match.group(1).lower()
                if cslug in ["bangle", "chains", "womens-necklace", "jewelry-set", "womens-jewelers-set", "womens-earrings", "anklet", "all", "mens-collection", "womens-ring"]:
                    return f"https://jwlbillion.com/collections/{cslug}"
                elif cslug in ["necklace", "necklaces", "pendant", "pendants", "choker"]:
                    return "https://jwlbillion.com/collections/womens-necklace"
                elif cslug in ["earring", "earrings"]:
                    return "https://jwlbillion.com/collections/womens-earrings"
                elif cslug in ["bracelet", "bracelets", "kada", "kadas"]:
                    return "https://jwlbillion.com/collections/bangle"
                return "https://jwlbillion.com/collections/all"

            # Fallback for weird URLs like /ladies-earrings/... or hallucinated routes
            if u.startswith("https://jwlbillion.com"):
                if valid_urls:
                    assigned_url = valid_urls[url_replacement_idx % len(valid_urls)]
                    url_replacement_idx += 1
                    return assigned_url
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
                elif "necklace" in u_lower or "pendant" in u_lower or "gale" in u_lower or "choker" in u_lower:
                    return "https://jwlbillion.com/collections/womens-necklace"
                return "https://jwlbillion.com"
            return u

        # Replace all store URLs with verified live URLs
        answer = re.sub(r'https?://(?:www\.)?jwlbillion\.com[^\s\)\],]+', sanitize_any_store_link, answer)

        # If LLM generated a product link or pitched a product without verified top_matches,
        # replace with a warm discovery question to build connection and qualify their requirement
        if not top_matches and (re.search(r'https?://jwlbillion\.com/products/[^\s\)\],]+', answer) or re.search(r'https?://jwlbillion\.com/collections/[^\s\)\],]+', answer)):
            logger.warning("[AI Service] Blocked hallucinated product recommendation with no live match.")
            answer = (
                "Hamare paas wedding, party aur daily wear ke liye bohot hi sundar gale ke necklaces aur chains uplabdh hain! ✨\n\n"
                "Aap ladies ke liye dekh rahe hain ya gents ke liye? Aur simple lightweight look chahiye ya thoda heavy set?"
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

        # Only attach recommended products if they were genuinely pitched or referenced in the AI's reply text!
        # NEVER dump products blindly if the customer was asking for support, order tracking, or general conversation.
        has_product_recommendation = bool(re.search(r'https?://(?:www\.)?jwlbillion\.com/products/', answer))
        if not has_product_recommendation:
            recommended_products = []

        # Keep unique products up to 3
        seen_p_ids = set()
        unique_rec_prods = []
        for p in recommended_products:
            p_id = p.get("id") or p.get("product_url")
            if p_id and p_id not in seen_p_ids:
                seen_p_ids.add(p_id)
                unique_rec_prods.append(p)

        first_prod = unique_rec_prods[0] if unique_rec_prods else None
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
