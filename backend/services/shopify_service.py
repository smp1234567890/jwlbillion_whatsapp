"""
Shopify Service
Handles order tracking lookups, customer order history, and Shopify webhook verification.
Uses standard HTTP calls with HMAC verification.
"""

import hmac
import hashlib
import base64
import logging
from typing import Optional, Dict, Any, List
import httpx
import config

logger = logging.getLogger("shopify_service")


def verify_shopify_hmac(body: bytes, hmac_header: str) -> bool:
    """
    Verifies Shopify webhook HMAC-SHA256 signature (Base64 encoded).
    """
    secret = config.SHOPIFY_CLIENT_SECRET or config.WEBHOOK_SECRET
    if not secret or not hmac_header:
        return False
    computed = base64.b64encode(
        hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("utf-8")
    return hmac.compare_digest(computed.strip(), hmac_header.strip())


def get_shopify_headers() -> Dict[str, str]:
    """
    Builds authorization headers for Shopify Admin REST API.
    """
    token = config.SHOPIFY_ACCESS_TOKEN or config.SHOPIFY_CLIENT_SECRET
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        headers["X-Shopify-Access-Token"] = token
    return headers


def find_order_by_name_or_id(order_query: str) -> Optional[Dict[str, Any]]:
    """
    Looks up an order by order name (e.g. #1001 or 1001) or Shopify Order ID.
    Returns parsed fulfillment status, courier, tracking code and items.
    """
    domain = config.SHOPIFY_STORE_DOMAIN
    if not domain:
        return None

    clean_num = order_query.strip().lstrip("#")
    url = f"https://{domain}/admin/api/2024-10/orders.json?name={clean_num}&status=any"
    
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.get(url, headers=get_shopify_headers())
            if resp.status_code == 200:
                orders = resp.json().get("orders", [])
                if orders:
                    return format_order_summary(orders[0])
            elif resp.status_code == 401:
                logger.warning("[Shopify] Unauthorized: Check SHOPIFY_ACCESS_TOKEN or custom app permissions.")
    except Exception as e:
        logger.error(f"[Shopify] Error looking up order {order_query}: {e}")
    return None


def find_recent_orders_by_phone(phone: str) -> List[Dict[str, Any]]:
    """
    Looks up recent orders for a customer's normalized phone number.
    """
    domain = config.SHOPIFY_STORE_DOMAIN
    if not domain:
        return []

    # Clean phone: +919876543210 -> check both raw and with +
    clean_phone = phone.strip()
    digits_only = "".join(filter(str.isdigit, clean_phone))
    
    url = f"https://{domain}/admin/api/2024-10/orders.json?status=any&limit=5"
    
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.get(url, headers=get_shopify_headers())
            if resp.status_code == 200:
                all_orders = resp.json().get("orders", [])
                matched = []
                for o in all_orders:
                    o_phone = "".join(filter(str.isdigit, str(o.get("phone") or o.get("customer", {}).get("phone") or "")))
                    if digits_only and digits_only in o_phone:
                        matched.append(format_order_summary(o))
                return matched
    except Exception as e:
        logger.error(f"[Shopify] Error searching orders by phone {phone}: {e}")
    return []


def format_order_summary(order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts key fulfillment and tracking details from a Shopify order object.
    """
    name = order.get("name") or f"#{order.get('order_number')}"
    financial_status = (order.get("financial_status") or "pending").capitalize()
    fulfillment_status = order.get("fulfillment_status") or "Unfulfilled"
    
    fulfillments = order.get("fulfillments") or []
    tracking_company = None
    tracking_number = None
    tracking_url = None
    
    if fulfillments:
        last_f = fulfillments[-1]
        tracking_company = last_f.get("tracking_company")
        tracking_number = last_f.get("tracking_number")
        tracking_url = last_f.get("tracking_url")
        if last_f.get("status"):
            fulfillment_status = last_f.get("status").capitalize()

    line_items = [
        f"{i.get('quantity')}x {i.get('title')}"
        for i in order.get("line_items", [])
    ]
    items_summary = ", ".join(line_items[:3])
    if len(line_items) > 3:
        items_summary += f" +{len(line_items) - 3} more"

    currency = order.get("currency") or "₹"
    total_price = order.get("total_price") or "0.00"

    return {
        "id": order.get("id"),
        "order_number": name,
        "financial_status": financial_status,
        "fulfillment_status": fulfillment_status.capitalize(),
        "tracking_company": tracking_company,
        "tracking_number": tracking_number,
        "tracking_url": tracking_url,
        "items_summary": items_summary,
        "total_price": total_price,
        "currency": currency,
        "created_at": order.get("created_at")
    }
