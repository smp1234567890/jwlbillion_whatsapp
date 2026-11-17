import re
import json
import logging
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("lead_intent_service")

# Ollama endpoint on host machine from within Docker container
OLLAMA_API_URL = "http://172.17.0.1:11434/api/generate"
QWEN_MODEL_NAME = "qwen2.5:3b"

# Keyword & Pattern Definitions for Lead Intent Classification
HIGH_INTENT_PATTERNS = [
    r"\b(price|pricing|cost|rate|rates|quote|quotation|fees?|charges?)\b",
    r"\b(buy|purchase|order|booking|book now|order now|checkout)\b",
    r"\b(discount|offer|coupon|deal|promo|best price|cheapest)\b",
    r"\b(catalog|catalogue|brochure|portfolio|samples?)\b",
    r"\b(available|in stock|ready stock|inventory)\b",
    r"\b(delivery|shipping|dispatch|courier|cod|cash on delivery)\b",
    r"\b(payment|pay|bank details|account details|upi|qr|google pay|phonepe)\b",
    r"\b(wholesale|bulk|distributor|dealership|resell|reseller)\b",
    r"\b(demo|appointment|meeting|visit|schedule|call me|urgent)\b",
    r"\b(how much|send details|share details|share price|need details|interested in)\b",
    r"\b(warranty|guarantee|specs|specifications|features)\b",
    r"\b(finalize|confirm order|proceed)\b",
]

INTEREST_PATTERNS = [
    r"\b(information|details?|clarify|question|query)\b",
    r"\b(where|location|address|office|store|shop|branch)\b",
    r"\b(size|color|colour|variety|types?|model|version)\b",
    r"\b(help|support|assist|how to|can you|tell me)\b",
    r"\b(service|services|products?|goods|items?)\b",
    r"\b(yes|yeah|sure|okay|ok|interested|looking for|want to know)\b",
    r"\b(timings?|hours?|open|working days?)\b",
]

NEGATIVE_PATTERNS = [
    r"\b(stop|unsubscribe|cancel|opt out|remove me|don'?t message|wrong number|not interested|no thanks|spam)\b",
]


def classify_intent_with_qwen(messages: List[Dict[str, Any]], timeout: float = 12.0) -> Optional[Dict[str, Any]]:
    """
    Invokes the local Qwen 2.5 LLM via Ollama to classify customer interest level,
    numerical score, and detected intent topics based on conversational context.
    """
    if not messages:
        return None

    # Format transcript lines (limit to last 8 messages for speed)
    recent_msgs = messages[-8:]
    transcript_lines = []
    for m in recent_msgs:
        sender = "Customer" if m.get("sender_type") == "CUSTOMER" else "Agent"
        txt = (m.get("text") or "").strip().replace("\n", " ")
        if txt:
            transcript_lines.append(f"{sender}: {txt[:200]}")

    if not transcript_lines:
        return None

    transcript_str = "\n".join(transcript_lines)

    prompt = f"""You are an expert sales qualification AI for JWL Billion jewelry.
Analyze this WhatsApp customer conversation:
{transcript_str}

Instructions:
1. Ignore automated ad greeting lines (e.g. "Hello! Can I get more info on this?"). Focus on what the customer actually asked for or replied with.
2. If customer asks about pricing, buying, catalog, delivery, wholesale, or resell, classify as HIGHLY_INTERESTED (score 70-100).
3. If customer asks general product questions, affirms interest, or engages actively, classify as INTERESTED (score 40-69).
4. If customer sends only the default ad greeting without any other response, classify as LOW_INTEREST (score 20-39).
5. If customer opts out or says not interested/stop, classify as NOT_INTERESTED (score 0-19).

Respond strictly with a single JSON object in this format:
{{
  "interest_level": "HIGHLY_INTERESTED" or "INTERESTED" or "LOW_INTEREST" or "NOT_INTERESTED",
  "interest_score": integer between 0 and 100,
  "detected_signals": ["keyword1", "keyword2"],
  "summary": "1 brief sentence summarizing customer intent"
}}"""

    payload = {
        "model": QWEN_MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_predict": 90
        }
    }

    try:
        req = urllib.request.Request(
            OLLAMA_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read().decode("utf-8"))
        raw_output = data.get("response", "").strip()

        parsed = json.loads(raw_output)
        level = parsed.get("interest_level", "LOW_INTEREST").upper()
        if level not in ["HIGHLY_INTERESTED", "INTERESTED", "LOW_INTEREST", "NOT_INTERESTED"]:
            level = "LOW_INTEREST"

        score = int(parsed.get("interest_score", 30))
        score = max(0, min(100, score))

        signals = parsed.get("detected_signals") or []
        if not isinstance(signals, list):
            signals = [str(signals)]

        summary = parsed.get("summary") or f"{level.replace('_', ' ').title()} lead"

        return {
            "interest_level": level,
            "interest_score": score,
            "detected_signals": signals[:6],
            "summary": summary,
            "analyzed_by": "qwen2.5"
        }
    except Exception as e:
        logger.debug(f"[Lead Intent Service] Qwen inference skipped/failed ({e}); using rule engine.")
        return None


def analyze_conversation_interest(messages: List[Dict[str, Any]], use_qwen: bool = False) -> Dict[str, Any]:
    """
    Analyzes the complete sequence of messages in a conversation.
    If use_qwen is True and Qwen responds, uses Qwen 2.5 classification.
    Otherwise uses the refined intent pattern engine.
    """
    if not messages:
        return {
            "is_client_initiated": False,
            "interest_level": "LOW_INTEREST",
            "interest_score": 0,
            "detected_signals": [],
            "inbound_count": 0,
            "outbound_count": 0,
            "client_first_message": None,
            "summary": "No messages in conversation."
        }

    # Sort messages chronologically
    sorted_msgs = sorted(messages, key=lambda m: m.get("created_at") or datetime.min)

    # 1. Determine initiation: Check the very first message
    first_msg = sorted_msgs[0]
    is_client_initiated = (first_msg.get("sender_type") == "CUSTOMER")

    # Filter inbound customer messages
    customer_msgs = [m for m in sorted_msgs if m.get("sender_type") == "CUSTOMER"]
    agent_msgs = [m for m in sorted_msgs if m.get("sender_type") == "AGENT"]

    inbound_count = len(customer_msgs)
    outbound_count = len(agent_msgs)

    if inbound_count == 0:
        return {
            "is_client_initiated": False,
            "interest_level": "OUTBOUND_ONLY",
            "interest_score": 0,
            "detected_signals": [],
            "inbound_count": 0,
            "outbound_count": outbound_count,
            "client_first_message": None,
            "summary": "Outbound only (no response from customer yet)."
        }

    client_first_message = customer_msgs[0].get("text") or ""

    # Try Qwen 2.5 if requested
    if use_qwen:
        qwen_res = classify_intent_with_qwen(sorted_msgs)
        if qwen_res:
            return {
                "is_client_initiated": is_client_initiated,
                "interest_level": qwen_res["interest_level"],
                "interest_score": qwen_res["interest_score"],
                "detected_signals": qwen_res["detected_signals"],
                "inbound_count": inbound_count,
                "outbound_count": outbound_count,
                "client_first_message": client_first_message,
                "summary": qwen_res["summary"],
                "analyzed_by": "qwen2.5"
            }

    all_customer_text = " ".join((m.get("text") or "").lower() for m in customer_msgs)

    # Check for hard negative / unsubscribe
    is_negative = any(re.search(pat, all_customer_text, re.IGNORECASE) for pat in NEGATIVE_PATTERNS)
    if is_negative and inbound_count <= 2:
        return {
            "is_client_initiated": is_client_initiated,
            "interest_level": "NOT_INTERESTED",
            "interest_score": 5,
            "detected_signals": ["opt_out_or_uninterested"],
            "inbound_count": inbound_count,
            "outbound_count": outbound_count,
            "client_first_message": client_first_message,
            "summary": "Lead indicated not interested or opted out."
        }

    # Signal Detection
    detected_signals = []
    high_intent_matches = 0
    for pat in HIGH_INTENT_PATTERNS:
        match = re.search(pat, all_customer_text, re.IGNORECASE)
        if match:
            high_intent_matches += 1
            matched_word = match.group(0).lower()
            if matched_word not in detected_signals:
                detected_signals.append(matched_word)

    interest_matches = 0
    for pat in INTEREST_PATTERNS:
        match = re.search(pat, all_customer_text, re.IGNORECASE)
        if match:
            interest_matches += 1
            matched_word = match.group(0).lower()
            if matched_word not in detected_signals:
                detected_signals.append(matched_word)

    # Scoring Algorithm
    score = 20  # Base score for any inbound engagement

    if is_client_initiated:
        score += 25  # Bonus for lead reaching out first

    # Message volume engagement
    if inbound_count >= 2:
        score += 15
    if inbound_count >= 4:
        score += 10

    # High intent signals (pricing, buying, catalog, delivery)
    score += min(high_intent_matches * 15, 30)

    # General interest signals
    score += min(interest_matches * 5, 15)

    # Cap score between 0 and 100
    score = max(0, min(100, score))

    # Classification
    if high_intent_matches >= 1 or score >= 70 or (is_client_initiated and inbound_count >= 2 and score >= 60):
        level = "HIGHLY_INTERESTED"
    elif interest_matches >= 1 or is_client_initiated or inbound_count >= 2 or score >= 40:
        level = "INTERESTED"
    else:
        level = "LOW_INTEREST"

    return {
        "is_client_initiated": is_client_initiated,
        "interest_level": level,
        "interest_score": score,
        "detected_signals": detected_signals[:6],  # top signals
        "inbound_count": inbound_count,
        "outbound_count": outbound_count,
        "client_first_message": client_first_message,
        "summary": f"{level.replace('_', ' ').title()} lead with {inbound_count} incoming messages."
    }
