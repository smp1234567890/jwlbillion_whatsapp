import logging
import re
import httpx
from typing import Optional
import config

logger = logging.getLogger("external_lead_service")

NEODOVE_WEBHOOK_URL = getattr(
    config,
    "NEODOVE_LEAD_WEBHOOK_URL",
    "https://d7f9432d-67a4-4897-95ea-d59e92b2df94.neodove.com/integration/custom/af2944a0-ebd9-490b-97e2-4625e4658bd5/leads"
)

def format_10_digit_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalizes phone numbers to standard 10 digits.
    Strips non-digit characters, leading +91, 91, or 0.
    """
    if not phone:
        return None
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) > 10 and digits.startswith("0"):
        digits = digits.lstrip("0")
    if len(digits) == 10:
        return digits
    return digits[-10:] if len(digits) >= 10 else digits


async def send_lead_to_neodove(name: str, phone: str, webhook_url: Optional[str] = None) -> bool:
    """
    Sends customer name and 10-digit number to NeoDove Open API endpoint.
    Runs asynchronously and logs result without raising exceptions to callers.
    """
    url = webhook_url or NEODOVE_WEBHOOK_URL
    if not url:
        logger.warning("[NeoDove Integration] Webhook URL not configured. Skipping lead dispatch.")
        return False

    standard_10_digit = format_10_digit_phone(phone)
    if not standard_10_digit or len(standard_10_digit) < 10:
        logger.warning(f"[NeoDove Integration] Invalid phone number '{phone}' (normalized: '{standard_10_digit}'). Skipping.")
        return False

    lead_name = (name or "WhatsApp Lead").strip()
    payload = {
        "name": lead_name,
        "number": standard_10_digit
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code in (200, 201, 202):
                logger.info(f"[NeoDove Integration] Successfully pushed lead '{lead_name}' ({standard_10_digit}) to NeoDove. Status: {response.status_code}")
                return True
            else:
                logger.error(f"[NeoDove Integration] Failed to push lead. Status: {response.status_code}, Body: {response.text[:200]}")
                return False
    except Exception as exc:
        logger.error(f"[NeoDove Integration] Error sending lead to NeoDove: {exc}")
        return False
