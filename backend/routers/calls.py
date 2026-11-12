import os
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import httpx
from sqlalchemy.orm import Session

from database import get_db
import auth
import models
import config

logger = logging.getLogger("calls_router")

# Global in-memory cache for pending call WebRTC events
PENDING_CALL_EVENTS = {}

router = APIRouter(prefix="/api/calls", tags=["calls"])

GRAPH_API_VERSION = "v21.0"

class SendCallPermissionRequest(BaseModel):
    customer_phone: str
    custom_message: Optional[str] = "We would like to call you via WhatsApp to help answer your questions directly."

class InitiateCallRequest(BaseModel):
    customer_phone: str
    sdp_offer: str

@router.get("/permission")
async def check_call_permission(
    phone: str = Query(..., description="Customer phone number with country code"),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Checks Meta Cloud API to verify if the business has permission to call this customer via WhatsApp.
    """
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    phone_id = config.WHATSAPP_PHONE_NUMBER_ID
    token = config.WHATSAPP_API_TOKEN

    if not phone_id or not token:
        raise HTTPException(status_code=500, detail="WhatsApp Cloud API credentials not configured")

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/call_permissions"
    params = {"user_wa_id": clean_phone}
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            data = resp.json()

            if resp.status_code != 200:
                logger.error(f"Error checking call permission for {clean_phone}: {data}")
                return {
                    "status": "error",
                    "permission_status": "unknown",
                    "can_request_permission": False,
                    "error": data.get("error", {}).get("message", "Failed to query Meta")
                }

            permission_info = data.get("permission", {})
            status_val = permission_info.get("status", "no_permission")
            # Meta returns 'temporary' (7-day permission) or 'permanent' when user tapped Allow
            if status_val in ["temporary", "permanent", "granted"]:
                status_val = "granted"
            actions = data.get("actions", [])
            can_request = any(a.get("action_name") == "send_call_permission_request" and a.get("can_perform_action") for a in actions)
            can_call = any(a.get("action_name") == "start_call" and a.get("can_perform_action") for a in actions)

            return {
                "status": "success",
                "phone": clean_phone,
                "permission_status": status_val, # "granted", "no_permission", "pending", "expired"
                "can_start_call": can_call or (status_val == "granted"),
                "can_request_permission": can_request,
                "raw": data
            }
    except Exception as e:
        logger.error(f"Exception checking call permissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/request-permission")
async def send_call_permission_request(
    req: SendCallPermissionRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sends an interactive call_permission_request message to the customer's WhatsApp chat.
    When the customer taps 'Allow', Meta grants calling permission for 7 days or permanent.
    """
    clean_phone = req.customer_phone.replace("+", "").replace(" ", "").replace("-", "")
    phone_id = config.WHATSAPP_PHONE_NUMBER_ID
    token = config.WHATSAPP_API_TOKEN

    if not phone_id or not token:
        raise HTTPException(status_code=500, detail="WhatsApp Cloud API credentials not configured")

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": "interactive",
        "interactive": {
            "type": "call_permission_request",
            "action": {
                "name": "call_permission_request"
            },
            "body": {
                "text": req.custom_message
            }
        }
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            data = resp.json()

            if resp.status_code != 200:
                logger.error(f"Failed to send call permission request to {clean_phone}: {data}")
                error_msg = data.get("error", {}).get("message", "Meta API Error")
                raise HTTPException(status_code=resp.status_code, detail=error_msg)

            return {
                "status": "success",
                "message": "Call permission request sent to customer's WhatsApp",
                "meta_response": data
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception sending call permission request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/initiate")
async def initiate_whatsapp_call(
    req: InitiateCallRequest,
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Initiates an outbound WhatsApp voice call using WebRTC SDP offer.
    """
    clean_phone = req.customer_phone.replace("+", "").replace(" ", "").replace("-", "")
    phone_id = config.WHATSAPP_PHONE_NUMBER_ID
    token = config.WHATSAPP_API_TOKEN

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/calls"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": clean_phone,
        "action": "connect",
        "session": {
            "sdp_type": "offer",
            "sdp": req.sdp_offer
        }
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            data = resp.json()

            if resp.status_code != 200:
                logger.error(f"Error initiating call: {data}")
                error_msg = data.get("error", {}).get("message", "Failed to initiate call")
                raise HTTPException(status_code=resp.status_code, detail=error_msg)

            calls_list = data.get("calls", [])
            extracted_cid = calls_list[0].get("id") if (calls_list and isinstance(calls_list, list)) else data.get("call_id")

            return {
                "status": "success",
                "call_id": extracted_cid,
                "meta_response": data
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class TerminateCallRequest(BaseModel):
    call_id: str

@router.get("/status")
async def get_call_status(
    call_id: str = Query(..., description="WhatsApp Call ID"),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Polls real-time WebRTC SDP answer and event updates for an active call.
    """
    event_data = PENDING_CALL_EVENTS.get(call_id)
    if event_data:
        return {"status": "success", "event": event_data}
    return {"status": "pending", "event": None}

@router.post("/terminate")
async def terminate_whatsapp_call(
    req: TerminateCallRequest,
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Terminates an active WhatsApp voice call.
    """
    phone_id = config.WHATSAPP_PHONE_NUMBER_ID
    token = config.WHATSAPP_API_TOKEN

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/calls"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "call_id": req.call_id,
        "action": "terminate"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            data = resp.json()
            return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error terminating call: {e}")
        return {"status": "error", "detail": str(e)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

