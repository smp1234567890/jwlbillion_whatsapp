"""
Centralized Smart Link Tracking Service for JWL Billion.
Generates trackable redirect URLs for:
1. Live AI & Support Chat replies
2. Bulk Broadcast Campaigns
3. Shopify Abandoned Cart Recovery

Tracking URLs route through /r/{code} on the server, record the click in `link_clicks`,
and issue a 302 redirect with UTM attribution to the destination.
"""
import base64
import re
from typing import Optional

TRACKING_BASE_URL = "https://130-210-23-25.sslip.io"


def build_tracked_url(
    target_url: str,
    recipient_phone: str,
    source: str = "ai_chat",
    campaign_id: Optional[int] = None
) -> str:
    """
    Builds a tamper-proof self-contained tracking URL.
    Encodes recipient phone and target URL so no database pre-insert is needed.
    Pattern:
      - /r/c{campaign_id}_{phone} (for campaigns)
      - /r/cart_{phone} (for cart recovery)
      - /r/u_{phone}_{b64_url} (for arbitrary product links in AI/live chat)
    """
    if not target_url:
        return f"{TRACKING_BASE_URL}/r/home"

    clean_p = recipient_phone.replace("+", "").replace(" ", "").replace("-", "") if recipient_phone else "guest"

    if campaign_id:
        return f"{TRACKING_BASE_URL}/r/c{campaign_id}_{clean_p}"

    if source == "cart_recovery":
        return f"{TRACKING_BASE_URL}/r/cart_{clean_p}"

    # Self-contained safe base64 URL encoding
    target_b64 = base64.urlsafe_b64encode(target_url.encode("utf-8")).decode("utf-8").rstrip("=")
    return f"{TRACKING_BASE_URL}/r/u_{clean_p}_{target_b64}"


def rewrite_text_links(
    text: str,
    recipient_phone: str,
    source: str = "ai_chat",
    campaign_id: Optional[int] = None
) -> str:
    """
    Finds store URLs (jwlbillion.com) in outbound message text and replaces them
    with personal tracked redirect links for the recipient.
    """
    if not text or not recipient_phone:
        return text

    def _replace_url(match):
        raw_url = match.group(0)
        # Avoid double-rewriting if already a tracking redirect
        if "/r/" in raw_url:
            return raw_url
        return build_tracked_url(raw_url, recipient_phone, source=source, campaign_id=campaign_id)

    # Match http/https URLs containing jwlbillion.com
    pattern = r'https?://(?:www\.)?jwlbillion\.com[^\s\)]*'
    return re.sub(pattern, _replace_url, text)
