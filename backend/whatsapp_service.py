import os
import logging
from datetime import datetime
from typing import Optional
import re
from dotenv import load_dotenv
import httpx
from sqlalchemy.orm import Session
from database import SessionLocal
import models

load_dotenv()
logger = logging.getLogger("whatsapp_service")
logging.basicConfig(level=logging.INFO)

import config
from services.phone_service import normalize_phone, InvalidPhoneNumberError
from services.policy_service import authorize_outbound_message
from services.pii_service import mask_phone

WHATSAPP_API_TOKEN = config.WHATSAPP_API_TOKEN
WHATSAPP_PHONE_NUMBER_ID = config.WHATSAPP_PHONE_NUMBER_ID
DAILY_MESSAGE_SEND_LIMIT = config.DAILY_MESSAGE_SEND_LIMIT
OPT_OUT_KEYWORDS = {
    "stop", "unsubscribe", "dnd", "cancel",
    "બંધ", "બંધ કરો", "સંદેશા બંધ કરો",  # Gujarati
    "रोको", "बंद करो", "मैसेज बंद करो"      # Hindi
}

META_API_URL = (
    f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    if WHATSAPP_PHONE_NUMBER_ID
    else ""
)


FIXED_DAILY_LIMIT = 200


def get_effective_daily_limit(db=None) -> int:
    """Returns the fixed daily limit of 200 outbound messages per day."""
    return DAILY_MESSAGE_SEND_LIMIT


def check_daily_limit(db) -> tuple[bool, int]:
    """
    Counts total messages dispatched today (UTC).
    Returns (is_under_limit, current_count).
    """
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    current_count = db.query(models.MessageLog).filter(
        models.MessageLog.created_at >= today_start,
        models.MessageLog.status.in_(["SENT", "SENT_SIMULATED", "DELIVERED", "READ"])
    ).count()

    effective_limit = get_effective_daily_limit(db)
    is_allowed = current_count < effective_limit
    return is_allowed, current_count


_TEMPLATE_META_SPECS: dict = {}


def get_template_spec(template_name: str, db: Optional[Session] = None) -> dict:
    """
    Resolves the exact approved language code and body parameter count for a Meta template.
    Guarantees:
    1. Language code matches Meta's translation (e.g. en_US, en_IN, gu) to prevent error #132001.
    2. Body parameter count matches Meta's placeholder count to prevent error #132000.
    """
    if template_name in _TEMPLATE_META_SPECS:
        return _TEMPLATE_META_SPECS[template_name]

    # 1. Check local DB
    if db:
        tmpl_rec = db.query(models.Template).filter(models.Template.template_name == template_name).first()
        if tmpl_rec and tmpl_rec.body_text and tmpl_rec.language:
            placeholders = set(re.findall(r"\{\{(\d+)\}\}", tmpl_rec.body_text or ""))
            spec = {
                "language": tmpl_rec.language,
                "body_param_count": len(placeholders),
                "source": "db"
            }
            _TEMPLATE_META_SPECS[template_name] = spec
            return spec

    # 2. Query Meta Graph API if credentials exist
    if WHATSAPP_API_TOKEN and config.WHATSAPP_BUSINESS_ACCOUNT_ID:
        try:
            url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{config.WHATSAPP_BUSINESS_ACCOUNT_ID}/message_templates?name={template_name}&limit=5"
            headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}"}
            with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    approved = [t for t in data if t.get("name") == template_name and t.get("status") == "APPROVED"]
                    target = approved[0] if approved else (data[0] if data else None)
                    if target:
                        meta_lang = target.get("language")
                        body_text = ""
                        for comp in target.get("components", []):
                            if comp.get("type") == "BODY":
                                body_text = comp.get("text", "")
                                break
                        placeholders = set(re.findall(r"\{\{(\d+)\}\}", body_text))
                        spec = {
                            "language": meta_lang,
                            "body_param_count": len(placeholders),
                            "source": "meta_api"
                        }
                        _TEMPLATE_META_SPECS[template_name] = spec

                        if db:
                            try:
                                existing = db.query(models.Template).filter(
                                    models.Template.template_name == template_name,
                                    models.Template.language == meta_lang
                                ).first()
                                if not existing:
                                    db.add(models.Template(
                                        template_name=template_name,
                                        category=target.get("category", "UTILITY"),
                                        language=meta_lang,
                                        body_text=body_text,
                                        status=target.get("status", "APPROVED")
                                    ))
                                    db.commit()
                            except Exception:
                                db.rollback()

                        return spec
        except Exception as e:
            logger.warning(f"Could not fetch template spec for '{template_name}' from Meta: {e}")

    # Fallback heuristics
    default_lang = "en_IN" if template_name in ["cart_recovery_v1", "template_1_entry", "scalifts_test__template"] else ("en_US" if template_name.startswith("appointment_") or template_name.startswith("auto_") else "en")
    default_count = 4 if template_name == "appointment_reminder_2" else (0 if template_name.startswith("appointment_") else 0)
    spec = {"language": default_lang, "body_param_count": default_count, "source": "fallback"}
    _TEMPLATE_META_SPECS[template_name] = spec
    return spec


def send_whatsapp_template(
    recipient_phone: str,
    template_name: str,
    language: str = "en",
    parameters: dict = None,
    coupon_code: str = None,
    button_parameters: list = None,
    campaign_id: int = None,
    sender_user: str = "System",
    idempotency_key: str = None,
    workflow_session_id: int = None,
    purpose: str = "utility",
    correlation_id: str = None,
    created_by_user_id: int = None,
    db: Optional[Session] = None
) -> dict:
    """
    Sends a WhatsApp message via Meta Cloud API or simulation mode.
    Guarded by:
    1. Phone normalization & validation
    2. Central authorize_and_create_outbound gate (Opt-Out, Consent Ledger, Daily Budget, Quiet Hours)
    3. Durable OutboundMessage state updates and audit event trail
    """
    owns_db = False
    if db is None:
        db = SessionLocal()
        owns_db = True
    try:
        try:
            clean_recipient_phone = normalize_phone(recipient_phone)
        except InvalidPhoneNumberError as pe:
            logger.error(f"🚨 [Invalid Phone] Cannot send message: {pe}")
            return {"status": "error", "message": f"Invalid recipient phone: {pe}"}

        # Resolve exact approved template specification (language and required param count)
        tmpl_spec = get_template_spec(template_name, db=db)
        if tmpl_spec.get("language"):
            # If user provided generic 'en' or None, promote to Meta approved code (e.g. en_US, en_IN)
            if not language or language == "en":
                language = tmpl_spec.get("language")

        # Normalize language code for Meta API (e.g. EN_US -> en_US)
        if language:
            parts = language.split("_")
            if len(parts) == 2:
                language = f"{parts[0].lower()}_{parts[1].upper()}"
            else:
                language = language.lower()

        # Generate idempotency key if not provided
        if not idempotency_key:
            import uuid
            idempotency_key = f"out_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:12]}"

        # Central Outbound Authorization & Durable Ledger Gate (WP2)
        from services.policy_service import authorize_and_create_outbound
        is_auth, outbound_rec, auth_reason = authorize_and_create_outbound(
            db=db,
            recipient_phone=clean_recipient_phone,
            idempotency_key=idempotency_key,
            message_kind="template",
            purpose=purpose,
            template_name=template_name,
            campaign_id=campaign_id,
            workflow_session_id=workflow_session_id,
            created_by_user_id=created_by_user_id,
            service_actor=sender_user,
            correlation_id=correlation_id,
            enforce_quiet_hours=True
        )

        # Check if already dispatched under this idempotency key — return existing Meta ID without re-calling API
        if outbound_rec and outbound_rec.status == "SENT":
            logger.info(f"🔁 [Idempotency] Message already dispatched for key '{idempotency_key}' (Meta ID: {outbound_rec.meta_message_id}). Skipping duplicate API call.")
            return {
                "status": "success",
                "message_id": outbound_rec.meta_message_id or f"dup_{int(datetime.utcnow().timestamp())}",
                "idempotent_replay": True
            }

        if not is_auth:
            logger.info(f"🚫 [Policy Blocked] Message to {mask_phone(clean_recipient_phone)} blocked: {auth_reason}")
            try:
                log_entry = models.MessageLog(
                    recipient_phone=clean_recipient_phone,
                    template_name=template_name,
                    campaign_id=campaign_id,
                    language=language,
                    sender_user=sender_user,
                    status="FAILED",
                    error_message=auth_reason
                )
                db.add(log_entry)
                if outbound_rec:
                    outbound_rec.status = "SKIPPED"
                    outbound_rec.error_message = auth_reason
                db.commit()
            except Exception:
                db.rollback()
            return {"status": "blocked", "reason": auth_reason}

        # Safe local mock mode when Meta credentials are empty
        if not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
            mock_wamid = f"mock_wamid_{int(datetime.utcnow().timestamp())}"
            logger.info(f"📱 [SIMULATION MODE] Template '{template_name}' ({language}) to {mask_phone(clean_recipient_phone)}")
            
            log_entry = models.MessageLog(
                recipient_phone=clean_recipient_phone,
                template_name=template_name,
                campaign_id=campaign_id,
                language=language,
                sender_user=sender_user,
                status="SENT_SIMULATED",
                meta_message_id=mock_wamid
            )
            db.add(log_entry)
            if outbound_rec:
                outbound_rec.status = "SENT"
                outbound_rec.meta_message_id = mock_wamid
                outbound_rec.dispatched_at = datetime.utcnow()
            db.commit()
            return {
                "status": "success_simulated",
                "message_id": mock_wamid,
                "info": "Meta API credentials not set. Simulated locally and logged in DB."
            }

        # Live Meta Cloud API Call
        headers = {
            "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        components = []
        if parameters:
            # Sort by key (param_1, param_2 ...) to guarantee correct positional order
            sorted_params = sorted(parameters.items(), key=lambda x: x[0])
            body_params = []
            for k, v in sorted_params:
                text_val = str(v).strip() if v is not None else ""
                if not text_val:
                    text_val = "-"
                body_params.append({"type": "text", "text": text_val})

            # Strictly align with Meta expected parameter count to eliminate #132000 errors
            expected_count = tmpl_spec.get("body_param_count", 0)
            if expected_count > 0:
                if len(body_params) > expected_count:
                    logger.info(f"Trimming {len(body_params)} body params to {expected_count} for template '{template_name}'")
                    body_params = body_params[:expected_count]
                elif len(body_params) < expected_count:
                    diff = expected_count - len(body_params)
                    for _ in range(diff):
                        body_params.append({"type": "text", "text": "-"})

            if body_params:
                components.append({
                    "type": "body",
                    "parameters": body_params
                })

        # Handle button parameters
        if button_parameters:
            for btn in button_parameters:
                components.append(btn)
        elif template_name in ["bazik_reengagement_v1"]:
            code_val = coupon_code
            if not code_val and parameters:
                code_val = parameters.get("param_2") or parameters.get("coupon_code")
            if not code_val:
                code_val = config.DEFAULT_COUPON_CODE
            components.append({
                "type": "button",
                "sub_type": "copy_code",
                "index": 0,
                "parameters": [
                    {
                        "type": "coupon_code",
                        "coupon_code": str(code_val).strip()
                    }
                ]
            })

        payload = {
            "messaging_product": "whatsapp",
            "to": clean_recipient_phone.replace("+", "").strip(),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": components
            }
        }

        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.post(META_API_URL, headers=headers, json=payload)
            data = resp.json()

            if resp.status_code == 200:
                msg_id = data.get("messages", [{}])[0].get("id", "")
                try:
                    log_entry = models.MessageLog(
                        recipient_phone=clean_recipient_phone,
                        template_name=template_name,
                        campaign_id=campaign_id,
                        language=language,
                        sender_user=sender_user,
                        status="SENT",
                        meta_message_id=msg_id
                    )
                    db.add(log_entry)
                    if outbound_rec:
                        outbound_rec.status = "SENT"
                        outbound_rec.meta_message_id = msg_id
                        outbound_rec.dispatched_at = datetime.utcnow()
                    db.commit()
                except Exception as log_err:
                    db.rollback()
                    logger.warning(f"Could not save MessageLog: {log_err}")

                # Also insert into ChatMessage for real-time 2-way live chat visibility
                try:
                    tmpl = db.query(models.Template).filter(models.Template.template_name == template_name).first()
                    body_content = tmpl.body_text if tmpl and tmpl.body_text else f"📢 Template: {template_name}"
                    if parameters:
                        for i, (k, val) in enumerate(parameters.items(), 1):
                            body_content = body_content.replace(f"{{{{{i}}}}}", str(val))
                    chat_entry = models.ChatMessage(
                        customer_phone=clean_recipient_phone,
                        sender_type="AGENT",
                        message_type="template",
                        text=body_content,
                        meta_message_id=msg_id,
                        status="SENT",
                        is_read=True
                    )
                    db.add(chat_entry)
                    db.commit()
                except Exception as c_err:
                    db.rollback()
                    logger.warning(f"Could not mirror template send to ChatMessage: {c_err}")

                return {"status": "success", "message_id": msg_id}
            else:
                err_dict = data.get("error", {})
                error_summary = err_dict.get("message") or f"HTTP {resp.status_code}"
                error_details = err_dict.get("error_data", {}).get("details")
                full_error_msg = f"{error_summary} ({error_details})" if error_details else error_summary
                log_entry = models.MessageLog(
                    recipient_phone=clean_recipient_phone,
                    template_name=template_name,
                    campaign_id=campaign_id,
                    language=language,
                    sender_user=sender_user,
                    status="FAILED",
                    error_message=full_error_msg
                )
                db.add(log_entry)
                if outbound_rec:
                    outbound_rec.status = "FAILED"
                    outbound_rec.error_message = full_error_msg
                db.commit()

                return {
                    "status": "failed",
                    "error": full_error_msg,
                    "reason": full_error_msg,
                    "code": err_dict.get("code")
                }

    except Exception as e:
        logger.error(f"Error in send_whatsapp_template: {e}", exc_info=True)
        try:
            log_entry = models.MessageLog(
                recipient_phone=recipient_phone,
                template_name=template_name,
                campaign_id=campaign_id,
                language=language,
                sender_user=sender_user,
                status="FAILED",
                error_message=str(e)
            )
            db.add(log_entry)
            db.commit()
        except Exception:
            pass
        return {"status": "error", "message": str(e), "error": str(e), "reason": str(e)}
    finally:
        if owns_db:
            db.close()


def create_meta_template(
    template_name: str,
    category: str,
    language: str,
    body_text: str,
    header_text: str = None,
    footer_text: str = None
) -> dict:
    """
    Submits a new WhatsApp message template to Meta Graph API.
    If Meta API credentials are not set, records in local simulation mode.
    """
    waba_id = config.WHATSAPP_BUSINESS_ACCOUNT_ID
    token = config.WHATSAPP_API_TOKEN

    if not waba_id or not token:
        logger.info(f"📝 [SIMULATION] Created template '{template_name}' locally (no Meta credentials).")
        return {
            "status": "APPROVED",
            "id": f"sim_template_{int(datetime.utcnow().timestamp())}",
            "category": category
        }

    url = f"{config.META_API_BASE_URL}/{waba_id}/message_templates"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    components = [
        {
            "type": "BODY",
            "text": body_text
        }
    ]

    if header_text:
        components.append({
            "type": "HEADER",
            "format": "TEXT",
            "text": header_text
        })

    if footer_text:
        components.append({
            "type": "FOOTER",
            "text": footer_text
        })

    payload = {
        "name": template_name.lower().replace(" ", "_"),
        "category": category.upper(),
        "language": language,
        "components": components
    }

    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.post(url, headers=headers, json=payload)
            data = resp.json()
            if resp.status_code in [200, 201]:
                return {
                    "status": data.get("status", "PENDING"),
                    "id": data.get("id"),
                    "category": data.get("category")
                }
            else:
                error_msg = data.get("error", {}).get("message", "Meta template submission failed")
                return {"error": error_msg, "status": "FAILED"}
    except Exception as e:
        logger.error(f"Error submitting template to Meta: {e}")
        return {"error": str(e), "status": "FAILED"}


def send_whatsapp_free_text(recipient_phone: str, message_text: str, sender_user: str = "Agent", db: Optional[Session] = None) -> dict:
    """
    Sends a free-form customer service text message (used within Meta's 24-hour service window).
    Falls back to simulation mode if API credentials are not set.
    """
    owns_db = False
    if db is None:
        db = SessionLocal()
        owns_db = True
    try:
        is_auth, auth_reason = authorize_outbound_message(
            db=db,
            recipient_phone=recipient_phone,
            message_type="free_text",
            sender_user=sender_user
        )
        if not is_auth:
            logger.warning(f"🚫 [Policy Blocked] Free-text to {mask_phone(recipient_phone)} blocked: {auth_reason}")
            try:
                log_entry = models.MessageLog(
                    recipient_phone=recipient_phone,
                    template_name="free_text_reply",
                    sender_user=sender_user,
                    status="FAILED",
                    error_message=auth_reason
                )
                db.add(log_entry)
                db.commit()
            except Exception:
                db.rollback()
            return {"status": "blocked", "reason": auth_reason}

        clean_phone = normalize_phone(recipient_phone)

        # Check if simulated or live
        if not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
            mock_id = f"sim_chat_{int(datetime.utcnow().timestamp())}"
            logger.info(f"💬 [SIMULATED 2-WAY CHAT] Agent sent to {mask_phone(clean_phone)}: '{message_text}'")
            return {
                "status": "success_simulated",
                "message_id": mock_id,
                "info": "Simulated locally without live Meta credentials"
            }

        headers = {
            "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone.replace("+", ""),
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message_text
            }
        }

        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.post(META_API_URL, headers=headers, json=payload)
            data = resp.json()
            if resp.status_code == 200:
                msg_id = data.get("messages", [{}])[0].get("id", "")
                return {"status": "success", "message_id": msg_id}
            else:
                error_info = str(data.get("error", {}))
                logger.error(f"Meta chat send error: {error_info}")
                return {"status": "failed", "error": error_info}
    except Exception as e:
        logger.error(f"Error in send_whatsapp_free_text: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if owns_db:
            db.close()
