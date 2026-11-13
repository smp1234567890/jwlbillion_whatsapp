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
from datetime import datetime
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
    Product URLs use the public custom domain (e.g. jwlbillion.com) instead of the myshopify backend domain.
    """
    domain = config.SHOPIFY_STORE_DOMAIN or "jewellers-fashion.myshopify.com"
    public_domain = getattr(config, "SHOPIFY_PUBLIC_DOMAIN", None) or "jwlbillion.com"
    public_domain = public_domain.replace("https://", "").replace("http://", "").rstrip("/")

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
                    shop_url = f"https://{public_domain}/products/{product_handle}" if product_handle else None

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


def sync_shopify_customers_and_orders(db) -> Dict[str, Any]:
    """
    Synchronizes customers and orders from the linked Shopify store into the Contact database.
    - Pulls customers and orders using Shopify Admin REST API.
    - Maps phone from customer, default address, or order billing/shipping address.
    - Aggregates accurate order counts, spent amounts, last order dates, cities, and order line items.
    """
    from services.phone_service import normalize_phone, InvalidPhoneNumberError
    import models

    domain = config.SHOPIFY_STORE_DOMAIN
    if not domain:
        return {"status": "error", "message": "SHOPIFY_STORE_DOMAIN is not configured"}

    headers = get_shopify_headers()
    synced_count = 0
    updated_count = 0
    errors = []

    try:
        with httpx.Client(timeout=30.0) as client:
            # 1. Fetch Orders from Shopify to build order history map by phone
            orders_url = f"https://{domain}/admin/api/2024-10/orders.json?status=any&limit=250"
            orders_resp = client.get(orders_url, headers=headers)
            orders_by_phone = {}
            if orders_resp.status_code == 200:
                orders = orders_resp.json().get("orders", [])
                for o in orders:
                    cust = o.get("customer") or {}
                    billing = o.get("billing_address") or {}
                    shipping = o.get("shipping_address") or {}
                    
                    phone_cands = [
                        o.get("phone"),
                        billing.get("phone"),
                        shipping.get("phone"),
                        cust.get("phone")
                    ]
                    # Map order to ALL valid phone numbers associated with it
                    matched_order_phones = set()
                    for pc in phone_cands:
                        if pc:
                            try:
                                cp = normalize_phone(str(pc))
                                if cp:
                                    matched_order_phones.add(cp)
                            except InvalidPhoneNumberError:
                                pass
                    for cp in matched_order_phones:
                        if cp not in orders_by_phone:
                            orders_by_phone[cp] = []
                        orders_by_phone[cp].append(o)

            # 2. Fetch Customers from Shopify
            cust_url = f"https://{domain}/admin/api/2024-10/customers.json?limit=250"
            cust_resp = client.get(cust_url, headers=headers)
            customers = []
            if cust_resp.status_code == 200:
                customers = cust_resp.json().get("customers", [])

            # Process customers first
            processed_phones = set()
            for c in customers:
                first = c.get("first_name") or ""
                last = c.get("last_name") or ""
                name = f"{first} {last}".strip() or None
                email = c.get("email") or None
                tags = c.get("tags") or None
                default_addr = c.get("default_address") or {}
                city = default_addr.get("city") or None
                state = default_addr.get("province") or None

                phone_cands = [
                    c.get("phone"),
                    default_addr.get("phone")
                ]
                # Also check addresses array
                for addr in c.get("addresses") or []:
                    if addr.get("phone"):
                        phone_cands.append(addr.get("phone"))

                clean_phone = None
                for pc in phone_cands:
                    if pc:
                        try:
                            clean_phone = normalize_phone(str(pc))
                            break
                        except InvalidPhoneNumberError:
                            pass

                if not clean_phone or clean_phone in processed_phones:
                    continue

                processed_phones.add(clean_phone)
                customer_orders = orders_by_phone.get(clean_phone, [])
                total_orders = max(c.get("orders_count", 0), len(customer_orders))
                
                # Determine last order date and info
                last_order_date = None
                last_order_info = None
                if customer_orders:
                    sorted_orders = sorted(customer_orders, key=lambda x: x.get("created_at") or "", reverse=True)
                    latest = sorted_orders[0]
                    created_str = latest.get("created_at")
                    if created_str:
                        try:
                            dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                            last_order_date = dt.replace(tzinfo=None)
                        except Exception:
                            pass
                    last_order_info = {
                        "order_id": str(latest.get("id")),
                        "order_number": str(latest.get("name")),
                        "total_price": float(latest.get("total_price") or 0.0),
                        "currency": latest.get("currency") or "INR",
                        "items_summary": ", ".join([item.get("title") or "Item" for item in (latest.get("line_items") or [])[:3]]),
                        "ordered_at": created_str
                    }

                # Upsert into Contact table
                contact = db.query(models.Contact).filter(models.Contact.phone == clean_phone).first()
                if contact:
                    if name and not contact.name:
                        contact.name = name[:100]
                    elif name and (contact.name in ["Valued Customer", "Customer", None]):
                        contact.name = name[:100]
                    if email and not contact.email:
                        contact.email = email[:120]
                    if city and not contact.city:
                        contact.city = city[:100]
                    if state and not contact.state:
                        contact.state = state[:100]
                    if total_orders > (contact.total_orders or 0):
                        contact.total_orders = total_orders
                    if last_order_date and (not contact.last_order_date or last_order_date > contact.last_order_date):
                        contact.last_order_date = last_order_date
                    if last_order_info:
                        attrs = dict(contact.custom_attributes or {})
                        attrs["last_order"] = last_order_info
                        attrs["shopify_customer_id"] = str(c.get("id"))
                        attrs["shopify_total_spent"] = str(c.get("total_spent", "0.00"))
                        contact.custom_attributes = attrs
                    updated_count += 1
                else:
                    attrs = {
                        "shopify_customer_id": str(c.get("id")),
                        "shopify_total_spent": str(c.get("total_spent", "0.00"))
                    }
                    if last_order_info:
                        attrs["last_order"] = last_order_info
                    contact = models.Contact(
                        phone=clean_phone,
                        name=name[:100] if name else None,
                        email=email[:120] if email else None,
                        city=city[:100] if city else None,
                        state=state[:100] if state else None,
                        tags=tags[:255] if tags else None,
                        total_orders=total_orders,
                        last_order_date=last_order_date,
                        is_active=True,
                        custom_attributes=attrs
                    )
                    db.add(contact)
                    synced_count += 1

            # Also ingest any order contacts that might not have a formal Customer record
            for clean_phone, customer_orders in orders_by_phone.items():
                if clean_phone in processed_phones:
                    continue
                sorted_orders = sorted(customer_orders, key=lambda x: x.get("created_at") or "", reverse=True)
                latest = sorted_orders[0]
                cust = latest.get("customer") or {}
                billing = latest.get("billing_address") or {}
                shipping = latest.get("shipping_address") or {}

                first = cust.get("first_name") or billing.get("first_name") or shipping.get("first_name") or ""
                last = cust.get("last_name") or billing.get("last_name") or shipping.get("last_name") or ""
                name = f"{first} {last}".strip() or None
                email = latest.get("email") or cust.get("email")
                city = shipping.get("city") or billing.get("city")
                state = shipping.get("province") or billing.get("province")

                last_order_date = None
                created_str = latest.get("created_at")
                if created_str:
                    try:
                        dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        last_order_date = dt.replace(tzinfo=None)
                    except Exception:
                        pass

                last_order_info = {
                    "order_id": str(latest.get("id")),
                    "order_number": str(latest.get("name")),
                    "total_price": float(latest.get("total_price") or 0.0),
                    "currency": latest.get("currency") or "INR",
                    "items_summary": ", ".join([item.get("title") or "Item" for item in (latest.get("line_items") or [])[:3]]),
                    "ordered_at": created_str
                }

                contact = db.query(models.Contact).filter(models.Contact.phone == clean_phone).first()
                if contact:
                    if name and not contact.name:
                        contact.name = name[:100]
                    if email and not contact.email:
                        contact.email = email[:120]
                    if city and not contact.city:
                        contact.city = city[:100]
                    if state and not contact.state:
                        contact.state = state[:100]
                    contact.total_orders = max(contact.total_orders or 0, len(customer_orders))
                    if last_order_date and (not contact.last_order_date or last_order_date > contact.last_order_date):
                        contact.last_order_date = last_order_date
                    attrs = dict(contact.custom_attributes or {})
                    attrs["last_order"] = last_order_info
                    contact.custom_attributes = attrs
                    updated_count += 1
                else:
                    contact = models.Contact(
                        phone=clean_phone,
                        name=name[:100] if name else None,
                        email=email[:120] if email else None,
                        city=city[:100] if city else None,
                        state=state[:100] if state else None,
                        total_orders=len(customer_orders),
                        last_order_date=last_order_date,
                        is_active=True,
                        custom_attributes={"last_order": last_order_info}
                    )
                    db.add(contact)
                    synced_count += 1

            db.commit()
            return {
                "status": "success",
                "synced_new": synced_count,
                "updated_existing": updated_count,
                "total_shopify_customers": len(customers),
                "total_shopify_orders": len(orders_by_phone)
            }
    except Exception as e:
        logger.error(f"[Shopify Sync] Error during customers and orders sync: {e}", exc_info=True)
        db.rollback()
        return {"status": "error", "error": str(e)}



