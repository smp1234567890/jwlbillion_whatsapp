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


_cached_access_token: Optional[str] = None
_token_expires_at: Optional[float] = None


def get_shopify_access_token() -> Optional[str]:
    """
    Returns a valid Shopify access token.
    If SHOPIFY_ACCESS_TOKEN is directly provided, returns it.
    Otherwise, if client_id and client_secret are provided, obtains a token via OAuth client_credentials grant
    and caches it until expiration.
    """
    global _cached_access_token, _token_expires_at
    import time

    if config.SHOPIFY_ACCESS_TOKEN:
        return config.SHOPIFY_ACCESS_TOKEN

    now = time.time()
    if _cached_access_token and _token_expires_at and (now < _token_expires_at - 60):
        return _cached_access_token

    domain = config.SHOPIFY_STORE_DOMAIN
    client_id = config.SHOPIFY_CLIENT_ID
    client_secret = config.SHOPIFY_CLIENT_SECRET

    if domain and client_id and client_secret:
        url = f"https://{domain}/admin/oauth/access_token"
        try:
            with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
                resp = client.post(url, json={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "client_credentials"
                })
                if resp.status_code == 200:
                    data = resp.json()
                    token = data.get("access_token")
                    expires_in = data.get("expires_in", 86400)
                    if token:
                        _cached_access_token = token
                        _token_expires_at = now + float(expires_in)
                        return _cached_access_token
                else:
                    logger.error(f"[Shopify OAuth] Failed getting access token: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"[Shopify OAuth] Exception during token retrieval: {e}")

    # Fallback to secret or None
    return client_secret or None


def get_shopify_headers() -> Dict[str, str]:
    """
    Builds authorization headers for Shopify Admin REST API.
    """
    token = get_shopify_access_token()
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
    Looks up recent orders for a customer's phone number.
    Uses Shopify Customer Search API first to get customer history,
    then queries recent orders by phone or shipping phone.
    Returns orders sorted newest first.
    """
    domain = config.SHOPIFY_STORE_DOMAIN
    if not domain:
        return []

    clean_phone = phone.strip()
    digits_only = "".join(filter(str.isdigit, clean_phone))
    last_10 = digits_only[-10:] if len(digits_only) >= 10 else digits_only
    if not last_10:
        return []

    headers = get_shopify_headers()
    matched_orders = []
    seen_order_ids = set()

    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            # 1. Search customer by phone number in Shopify
            cust_url = f"https://{domain}/admin/api/2024-10/customers/search.json?query={last_10}"
            cust_resp = client.get(cust_url, headers=headers)
            if cust_resp.status_code == 200:
                customers = cust_resp.json().get("customers", [])
                for cust in customers:
                    cid = cust.get("id")
                    if not cid:
                        continue
                    # Fetch orders for this customer (up to 5, status=any)
                    c_orders_url = f"https://{domain}/admin/api/2024-10/customers/{cid}/orders.json?status=any&limit=5"
                    co_resp = client.get(c_orders_url, headers=headers)
                    if co_resp.status_code == 200:
                        for o in co_resp.json().get("orders", []):
                            oid = o.get("id")
                            if oid and oid not in seen_order_ids:
                                seen_order_ids.add(oid)
                                matched_orders.append(format_order_summary(o))

            # 2. If no orders found via customer search, fallback to direct recent orders scan
            if not matched_orders:
                orders_url = f"https://{domain}/admin/api/2024-10/orders.json?status=any&limit=20"
                orders_resp = client.get(orders_url, headers=headers)
                if orders_resp.status_code == 200:
                    for o in orders_resp.json().get("orders", []):
                        oid = o.get("id")
                        if oid in seen_order_ids:
                            continue
                        phones_to_check = [
                            o.get("phone") or "",
                            (o.get("customer") or {}).get("phone") or "",
                            (o.get("shipping_address") or {}).get("phone") or "",
                            (o.get("billing_address") or {}).get("phone") or ""
                        ]
                        for p in phones_to_check:
                            p_digits = "".join(filter(str.isdigit, str(p)))
                            if last_10 in p_digits:
                                seen_order_ids.add(oid)
                                matched_orders.append(format_order_summary(o))
                                break

    except Exception as e:
        logger.error(f"[Shopify] Error searching orders by phone {phone}: {e}")

    # Sort newest first based on created_at or id
    matched_orders.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return matched_orders


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


def fetch_shopify_products(limit: int = 250) -> Dict[str, Any]:
    """
    Fetches all live products directly from Shopify without storing them in the DB.
    First tries public storefront products.json (always available for the configured domain),
    and falls back to Admin API if credentials exist.
    """
    domain = config.SHOPIFY_STORE_DOMAIN or "jewellers-fashion.myshopify.com"
    url = f"https://{domain}/products.json?limit={min(limit, 250)}"

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                raw_products = resp.json().get("products", [])
                formatted = []
                for p in raw_products:
                    variants = p.get("variants") or []
                    first_var = variants[0] if variants else {}
                    images = p.get("images") or []
                    image_url = images[0].get("src") if images else None
                    
                    price = first_var.get("price") or "0"
                    compare_at_price = first_var.get("compare_at_price")
                    available = first_var.get("available", True)
                    
                    product_handle = p.get("handle") or ""
                    shop_url = f"https://{domain}/products/{product_handle}" if product_handle else None

                    formatted.append({
                        "id": p.get("id"),
                        "title": p.get("title"),
                        "handle": product_handle,
                        "vendor": p.get("vendor"),
                        "product_type": p.get("product_type"),
                        "tags": p.get("tags") or [],
                        "price": price,
                        "compare_at_price": compare_at_price,
                        "available": available,
                        "variants_count": len(variants),
                        "image_url": image_url,
                        "all_images": [img.get("src") for img in images if img.get("src")],
                        "published_at": p.get("published_at"),
                        "created_at": p.get("created_at"),
                        "product_url": shop_url
                    })

                return {
                    "status": "success",
                    "store_domain": domain,
                    "total_count": len(formatted),
                    "products": formatted
                }
            else:
                logger.error(f"[Shopify Products] Failed to fetch: {resp.status_code} {resp.text[:200]}")
                return {
                    "status": "error",
                    "store_domain": domain,
                    "total_count": 0,
                    "products": [],
                    "error": f"Shopify responded with status {resp.status_code}"
                }
    except Exception as e:
        logger.error(f"[Shopify Products] Exception: {e}")
        return {
            "status": "error",
            "store_domain": domain,
            "total_count": 0,
            "products": [],
            "error": str(e)
        }


