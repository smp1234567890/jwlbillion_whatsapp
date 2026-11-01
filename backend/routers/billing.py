"""
Billing Router
Fetches live Meta WhatsApp Business Account (WABA) billing and conversation analytics,
and calculates granular costs per campaign, per automation rule, and monthly cycle totals
based on official Meta conversation pricing (INR rates for Marketing, Utility, Authentication, Service).
"""

import logging
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

import auth
import models
import config
from database import get_db

logger = logging.getLogger("billing_router")

router = APIRouter(prefix="/api/billing", tags=["Billing & Costs"])

# Official Meta WhatsApp Cloud API Rates for India (IN) in INR:
# Marketing: ₹0.86 per delivered conversation / template dispatch
# Utility: ₹0.125 per delivered template
# Authentication: ₹0.125
# Service / Free-tier / User-initiated: ₹0.00 (within 1,000 free service convs / 24h window)
META_INDIA_RATES_INR = {
    "MARKETING": 0.86,
    "UTILITY": 0.125,
    "AUTHENTICATION": 0.125,
    "SERVICE": 0.00
}


def get_template_category_map(db: Session) -> Dict[str, str]:
    """Returns mapping of template_name -> category (MARKETING, UTILITY, AUTHENTICATION)."""
    tmpls = db.query(models.Template.template_name, models.Template.category).all()
    res = {}
    for name, cat in tmpls:
        if name:
            res[name.strip().lower()] = (cat or "MARKETING").strip().upper()
    return res


@router.get("/summary")
def get_billing_summary(
    month: Optional[str] = Query(None, description="Month in YYYY-MM format, defaults to current month"),
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """
    Returns monthly billing overview:
    - Meta WABA details (currency, account review status, live balance/spend if exposed by Meta)
    - Total monthly cost breakdown (Marketing vs Utility)
    - Cost per Campaign
    - Cost per Automation Rule
    - Daily spend trend
    """
    # 1. Resolve date window for requested month
    now = datetime.utcnow()
    if month:
        try:
            target_start = datetime.strptime(f"{month}-01", "%Y-%m-%d")
        except ValueError:
            target_start = datetime(now.year, now.month, 1)
    else:
        target_start = datetime(now.year, now.month, 1)

    # Next month start for cutoff
    if target_start.month == 12:
        target_end = datetime(target_start.year + 1, 1, 1)
    else:
        target_end = datetime(target_start.year, target_start.month + 1, 1)

    # 2. Fetch live WABA info from Meta Graph API
    waba_info = {
        "waba_id": config.WHATSAPP_BUSINESS_ACCOUNT_ID,
        "name": "JWL Billion",
        "currency": "INR",
        "timezone": "Asia/Kolkata",
        "account_status": "APPROVED",
        "connected_phone": config.WHATSAPP_PHONE_NUMBER_ID,
        "meta_live_connected": False
    }

    if config.WHATSAPP_API_TOKEN and config.WHATSAPP_BUSINESS_ACCOUNT_ID:
        try:
            waba_url = f"https://graph.facebook.com/v19.0/{config.WHATSAPP_BUSINESS_ACCOUNT_ID}"
            r = httpx.get(
                waba_url,
                params={"fields": "id,name,currency,timezone_id,account_review_status"},
                headers={"Authorization": f"Bearer {config.WHATSAPP_API_TOKEN}"},
                timeout=5.0
            )
            if r.status_code == 200:
                data = r.json()
                waba_info["waba_id"] = data.get("id", waba_info["waba_id"])
                waba_info["name"] = data.get("name", waba_info["name"])
                waba_info["currency"] = data.get("currency", waba_info["currency"])
                waba_info["account_status"] = data.get("account_review_status", waba_info["account_status"])
                waba_info["meta_live_connected"] = True
        except Exception as e:
            logger.warning(f"Meta WABA query failed: {e}")

    # 3. Query all MessageLogs for this billing cycle
    # Note: Meta only charges for DELIVERED and READ template conversations (FAILED messages are not billed by Meta).
    category_map = get_template_category_map(db)

    logs = (
        db.query(
            models.MessageLog.id,
            models.MessageLog.campaign_id,
            models.MessageLog.template_name,
            models.MessageLog.sender_user,
            models.MessageLog.status,
            models.MessageLog.created_at
        )
        .filter(
            models.MessageLog.created_at >= target_start,
            models.MessageLog.created_at < target_end
        )
        .all()
    )

    # Fetch all campaigns and automations for names
    campaigns = {c.id: c for c in db.query(models.Campaign).all()}
    automation_rules = {r.id: r for r in db.query(models.AutomationRule).all()}

    # Initialize aggregations
    total_messages_logged = len(logs)
    total_billable_count = 0
    total_marketing_cost = 0.0
    total_utility_cost = 0.0

    campaign_costs: Dict[int, Dict[str, Any]] = {}
    automation_costs: Dict[str, Dict[str, Any]] = {}
    daily_spend: Dict[str, float] = {}

    for l in logs:
        st = (l.status or "").upper()
        # Only DELIVERED and READ are billable conversations on WhatsApp Cloud API
        is_billable = st in ["DELIVERED", "READ"]

        tmpl_key = (l.template_name or "").strip().lower()
        cat = category_map.get(tmpl_key, "MARKETING")
        unit_rate = META_INDIA_RATES_INR.get(cat, 0.86)

        day_str = l.created_at.strftime("%Y-%m-%d") if l.created_at else target_start.strftime("%Y-%m-%d")
        if day_str not in daily_spend:
            daily_spend[day_str] = 0.0

        if is_billable:
            total_billable_count += 1
            if cat == "MARKETING":
                total_marketing_cost += unit_rate
            else:
                total_utility_cost += unit_rate

            daily_spend[day_str] += unit_rate

        # A. Group by Campaign
        if l.campaign_id:
            cid = l.campaign_id
            if cid not in campaign_costs:
                camp_obj = campaigns.get(cid)
                campaign_costs[cid] = {
                    "campaign_id": cid,
                    "title": camp_obj.title if camp_obj else f"Campaign #{cid}",
                    "template_name": l.template_name,
                    "category": cat,
                    "rate_per_msg": unit_rate,
                    "total_recipients": 0,
                    "delivered_count": 0,
                    "failed_count": 0,
                    "estimated_cost_inr": 0.0,
                    "created_at": camp_obj.created_at.isoformat() if camp_obj and camp_obj.created_at else None
                }
            campaign_costs[cid]["total_recipients"] += 1
            if is_billable:
                campaign_costs[cid]["delivered_count"] += 1
                campaign_costs[cid]["estimated_cost_inr"] += unit_rate
            elif st == "FAILED":
                campaign_costs[cid]["failed_count"] += 1

        # B. Group by Automation (sender_user starting with "Rule:", "Journey:", "Cart Recovery", or "Abandoned Cart")
        sender = l.sender_user or "System"
        is_automation = any(k in sender.lower() for k in ["rule", "journey", "cart", "abandoned", "automation"]) or (l.campaign_id is None and "campaign" not in sender.lower())
        if is_automation and not l.campaign_id:
            auto_name = sender
            if auto_name not in automation_costs:
                automation_costs[auto_name] = {
                    "automation_name": auto_name,
                    "template_name": l.template_name,
                    "category": cat,
                    "rate_per_msg": unit_rate,
                    "total_triggered": 0,
                    "delivered_count": 0,
                    "estimated_cost_inr": 0.0
                }
            automation_costs[auto_name]["total_triggered"] += 1
            if is_billable:
                automation_costs[auto_name]["delivered_count"] += 1
                automation_costs[auto_name]["estimated_cost_inr"] += unit_rate

    # Format campaign and automation lists
    campaigns_list = sorted(list(campaign_costs.values()), key=lambda x: x["estimated_cost_inr"], reverse=True)
    automations_list = sorted(list(automation_costs.values()), key=lambda x: x["estimated_cost_inr"], reverse=True)

    # Round costs to 2 decimal places
    for c in campaigns_list:
        c["estimated_cost_inr"] = round(c["estimated_cost_inr"], 2)
    for a in automations_list:
        a["estimated_cost_inr"] = round(a["estimated_cost_inr"], 2)

    total_cost_inr = round(total_marketing_cost + total_utility_cost, 2)

    # Sort daily spend by date
    daily_spend_list = [
        {"date": d, "cost_inr": round(amt, 2)}
        for d, amt in sorted(daily_spend.items())
    ]

    return {
        "billing_cycle": {
            "month": target_start.strftime("%B %Y"),
            "start_date": target_start.strftime("%Y-%m-%d"),
            "end_date": (target_end - timedelta(days=1)).strftime("%Y-%m-%d"),
        },
        "waba_info": waba_info,
        "rates": {
            "currency": "INR (₹)",
            "marketing": META_INDIA_RATES_INR["MARKETING"],
            "utility": META_INDIA_RATES_INR["UTILITY"],
            "authentication": META_INDIA_RATES_INR["AUTHENTICATION"]
        },
        "totals": {
            "total_cost_inr": total_cost_inr,
            "total_billable_conversations": total_billable_count,
            "total_messages_dispatched": total_messages_logged,
            "marketing_cost_inr": round(total_marketing_cost, 2),
            "utility_cost_inr": round(total_utility_cost, 2)
        },
        "campaigns": campaigns_list,
        "automations": automations_list,
        "daily_spend": daily_spend_list
    }
