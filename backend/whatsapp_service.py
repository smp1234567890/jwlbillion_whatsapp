import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
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
                "header_type": (tmpl_rec.header_type or "NONE").upper(),
                "sample_values": tmpl_rec.sample_values or {},
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
                        header_type = "NONE"
                        for comp in target.get("components", []):
                            if comp.get("type") == "HEADER":
                                header_type = (comp.get("format") or "TEXT").upper()
                            elif comp.get("type") == "BODY":
                                body_text = comp.get("text", "")

                        placeholders = set(re.findall(r"\{\{(\d+)\}\}", body_text))
                        spec = {
                            "language": meta_lang,
                            "body_param_count": len(placeholders),
                            "header_type": header_type,
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
    header_media: dict = None,
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
            logger.error(f"[Invalid Phone] Cannot send message: {pe}")
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
            logger.info(f"[Idempotency] Message already dispatched for key '{idempotency_key}' (Meta ID: {outbound_rec.meta_message_id}). Skipping duplicate API call.")
            return {
                "status": "success",
                "message_id": outbound_rec.meta_message_id or f"dup_{int(datetime.utcnow().timestamp())}",
                "idempotent_replay": True
            }

        if not is_auth:
            logger.info(f"[Policy Blocked] Message to {mask_phone(clean_recipient_phone)} blocked: {auth_reason}")
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
            logger.info(f"[SIMULATION MODE] Template '{template_name}' ({language}) to {mask_phone(clean_recipient_phone)}")
            
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

        # 1. Header Media Component (IMAGE, VIDEO, DOCUMENT, LOCATION)
        expected_header_type = (tmpl_spec.get("header_type") or "NONE").upper()
        if expected_header_type in ["IMAGE", "VIDEO", "DOCUMENT", "LOCATION"]:
            media_info = header_media or {}
            # Fall back to template sample values if not passed directly in call
            if not media_info and tmpl_spec.get("sample_values"):
                sv = tmpl_spec["sample_values"]
                media_info = {
                    "url": sv.get("header_url"),
                    "media_id": sv.get("header_handle") if not sv.get("header_url") else None,
                    "latitude": sv.get("latitude"),
                    "longitude": sv.get("longitude"),
                    "name": sv.get("location_name")
                }

            header_param = None
            raw_url = media_info.get("url")
            # Automatically prefix relative server upload paths with the public server domain
            if raw_url and raw_url.startswith("/uploads/"):
                raw_url = f"https://130-210-12-142.sslip.io{raw_url}"

            # Helper to get or upload Meta media_id if an upload path or raw_url is provided
            def _resolve_meta_id(mime: str, default_name: str) -> Optional[str]:
                if media_info.get("media_id"):
                    return media_info["media_id"]
                path_or_url = media_info.get("url")
                if not path_or_url:
                    return None
                # Check if it points to a local file in uploads/
                local_fpath = None
                if path_or_url.startswith("https://130-210-12-142.sslip.io/uploads/"):
                    local_fpath = os.path.join("uploads", path_or_url.split("/uploads/")[-1])
                elif path_or_url.startswith("/uploads/"):
                    local_fpath = os.path.join("uploads", path_or_url[len("/uploads/"):])
                elif os.path.exists(path_or_url):
                    local_fpath = path_or_url

                if local_fpath and os.path.exists(local_fpath):
                    try:
                        with open(local_fpath, "rb") as f_in:
                            b = f_in.read()
                        up_res = upload_media_to_meta(b, mime, os.path.basename(local_fpath) or default_name)
                        if up_res.get("status") == "success" and up_res.get("media_id"):
                            return up_res["media_id"]
                    except Exception as e:
                        logger.warning(f"Failed to auto-upload media to Meta: {e}")
                return None

            if expected_header_type == "IMAGE":
                img_obj = {}
                meta_id = _resolve_meta_id("image/jpeg", "image.jpg")
                if meta_id:
                    img_obj["id"] = meta_id
                elif raw_url:
                    img_obj["link"] = raw_url
                else:
                    img_obj["link"] = "https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=800&q=80"
                header_param = {"type": "image", "image": img_obj}

            elif expected_header_type == "VIDEO":
                vid_obj = {}
                meta_id = _resolve_meta_id("video/mp4", "video.mp4")
                if meta_id:
                    vid_obj["id"] = meta_id
                elif raw_url:
                    vid_obj["link"] = raw_url
                else:
                    vid_obj["link"] = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"
                header_param = {"type": "video", "video": vid_obj}

            elif expected_header_type == "DOCUMENT":
                doc_obj = {}
                meta_id = _resolve_meta_id("application/pdf", "document.pdf")
                if meta_id:
                    doc_obj["id"] = meta_id
                elif raw_url:
                    doc_obj["link"] = raw_url
                else:
                    doc_obj["link"] = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
                if media_info.get("filename"):
                    doc_obj["filename"] = media_info["filename"]
                header_param = {"type": "document", "document": doc_obj}

            elif expected_header_type == "LOCATION":
                loc_obj = {
                    "latitude": str(media_info.get("latitude") or "21.1702"),
                    "longitude": str(media_info.get("longitude") or "72.8311"),
                    "name": str(media_info.get("name") or config.BRAND_NAME),
                    "address": str(media_info.get("address") or (config.STORE_LOCATION or "Surat, Gujarat"))
                }
                header_param = {"type": "location", "location": loc_obj}

            if header_param:
                components.append({
                    "type": "header",
                    "parameters": [header_param]
                })

        # 2. Body Component
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
                    body_content = tmpl.body_text if tmpl and tmpl.body_text else f"Template: {template_name}"
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
    footer_text: str = None,
    sub_type: str = "DEFAULT",
    header_type: str = "NONE",
    buttons: Optional[List[dict]] = None,
    sample_values: Optional[dict] = None,
    validity_period_minutes: Optional[int] = None,
    auth_config: Optional[dict] = None
) -> dict:
    """
    Submits a rich WhatsApp message template to Meta Graph API.
    Handles Marketing, Utility, and Authentication categories,
    Header formats (TEXT, IMAGE, VIDEO, DOCUMENT, LOCATION),
    Review samples (Meta required when variables are present),
    Buttons (Quick reply, URL, Phone, Copy Code, Flows),
    and TTL validity period.
    Falls back to simulation mode if API credentials are not set.
    """
    waba_id = config.WHATSAPP_BUSINESS_ACCOUNT_ID
    token = config.WHATSAPP_API_TOKEN

    category_clean = (category or "MARKETING").upper()

    if not waba_id or not token:
        logger.info(f"[SIMULATION] Created template '{template_name}' locally ({category_clean} - {sub_type}).")
        return {
            "status": "APPROVED",
            "id": f"sim_template_{int(datetime.utcnow().timestamp())}",
            "category": category_clean
        }

    url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{waba_id}/message_templates"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    components = []

    # 1. HEADER Component
    norm_header_type = (header_type or "NONE").upper()
    if norm_header_type == "TEXT" and header_text:
        header_comp = {
            "type": "HEADER",
            "format": "TEXT",
            "text": header_text
        }
        # If header contains variables, add sample
        header_matches = re.findall(r"\{\{(\d+)\}\}", header_text)
        if header_matches:
            samples = []
            if sample_values and "header" in sample_values:
                samples = sample_values["header"]
            if not samples:
                samples = ["Sample Header"]
            header_comp["example"] = {"header_text": samples}
        components.append(header_comp)
    elif norm_header_type in ["IMAGE", "VIDEO", "DOCUMENT", "LOCATION"]:
        header_comp = {
            "type": "HEADER",
            "format": norm_header_type
        }
        if sample_values and "header_handle" in sample_values:
            header_comp["example"] = {"header_handle": [sample_values["header_handle"]]}
        components.append(header_comp)
    elif header_text and norm_header_type == "NONE":
        # Backward compatibility for plain header text
        components.append({
            "type": "HEADER",
            "format": "TEXT",
            "text": header_text
        })

    # 2. BODY Component
    body_comp = {
        "type": "BODY",
        "text": body_text
    }
    # Check for body variable placeholders {{1}}, {{2}}...
    body_matches = sorted(list(set(re.findall(r"\{\{(\d+)\}\}", body_text or ""))), key=lambda x: int(x))
    if body_matches:
        samples = []
        if sample_values and "body" in sample_values:
            samples = sample_values["body"]
        if not samples or len(samples) < len(body_matches):
            # Fallback default samples if none provided so Meta doesn't reject
            samples = [f"sample_{i}" for i in range(1, len(body_matches) + 1)]
        body_comp["example"] = {"body_text": [samples]}
    components.append(body_comp)

    # 3. FOOTER Component
    if footer_text:
        components.append({
            "type": "FOOTER",
            "text": footer_text
        })

    # 4. BUTTONS Component
    if buttons and isinstance(buttons, list) and len(buttons) > 0:
        meta_buttons = []
        for btn in buttons[:10]:
            b_type = (btn.get("type") or "QUICK_REPLY").upper()
            text_val = btn.get("text") or "Button"

            if b_type in ["QUICK_REPLY", "CUSTOM"]:
                meta_buttons.append({
                    "type": "QUICK_REPLY",
                    "text": text_val
                })
            elif b_type in ["URL", "VISIT_WEBSITE"]:
                url_btn = {
                    "type": "URL",
                    "text": text_val,
                    "url": btn.get("url", "https://example.com")
                }
                if "{{" in btn.get("url", ""):
                    url_sample = btn.get("example") or ["order123"]
                    url_btn["example"] = url_sample if isinstance(url_sample, list) else [url_sample]
                meta_buttons.append(url_btn)
            elif b_type in ["PHONE_NUMBER", "CALL_PHONE"]:
                meta_buttons.append({
                    "type": "PHONE_NUMBER",
                    "text": text_val,
                    "phone_number": btn.get("phone_number", "+919876543210")
                })
            elif b_type in ["COPY_CODE", "OTP"]:
                meta_buttons.append({
                    "type": "COPY_CODE",
                    "example": btn.get("example") or "OFFER20"
                })
            elif b_type in ["FLOW", "COMPLETE_FLOW"]:
                flow_btn = {
                    "type": "FLOW",
                    "text": text_val,
                    "navigate_screen": btn.get("navigate_screen", "START")
                }
                if btn.get("flow_id"):
                    flow_btn["flow_id"] = btn.get("flow_id")
                meta_buttons.append(flow_btn)

        if meta_buttons:
            components.append({
                "type": "BUTTONS",
                "buttons": meta_buttons
            })

    payload = {
        "name": template_name.lower().replace(" ", "_"),
        "category": category_clean,
        "language": language,
        "components": components
    }

    # TTL Validity Period (Utility & Authentication)
    if validity_period_minutes and validity_period_minutes > 0:
        payload["message_send_ttl_seconds"] = int(validity_period_minutes) * 60

    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.post(url, headers=headers, json=payload)
            data = resp.json()
            if resp.status_code in [200, 201]:
                return {
                    "status": data.get("status", "PENDING"),
                    "id": data.get("id"),
                    "category": data.get("category", category_clean)
                }
            else:
                err_obj = data.get("error", {})
                err_msg = err_obj.get("error_user_msg") or err_obj.get("message") or "Meta template submission failed"
                err_title = err_obj.get("error_user_title")
                err_subcode = err_obj.get("error_subcode")
                
                full_detail = err_msg
                if err_title:
                    full_detail = f"{err_title}: {err_msg}"
                if err_subcode:
                    full_detail += f" (Meta Subcode: {err_subcode})"
                
                logger.error(f"[Meta Template Rejected] {data}")
                return {"error": full_detail, "status": "FAILED", "raw_error": err_obj}
    except Exception as e:
        logger.error(f"Error submitting template to Meta: {e}")
        return {"error": str(e), "status": "FAILED"}


def send_whatsapp_free_text(
    recipient_phone: str,
    message_text: str,
    sender_user: str = "Agent",
    db: Optional[Session] = None,
    bypass_policy: bool = False
) -> dict:
    """
    Sends a free-form customer service text message (used within Meta's 24-hour service window).
    Falls back to simulation mode if API credentials are not set.
    """
    owns_db = False
    if db is None:
        db = SessionLocal()
        owns_db = True
    try:
        if not bypass_policy:
            is_auth, auth_reason = authorize_outbound_message(
                db=db,
                recipient_phone=recipient_phone,
                message_type="free_text",
                sender_user=sender_user
            )
            if not is_auth:
                logger.warning(f"[Policy Blocked] Free-text to {mask_phone(recipient_phone)} blocked: {auth_reason}")
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
            logger.info(f"[SIMULATED 2-WAY CHAT] Agent sent to {mask_phone(clean_phone)}: '{message_text}'")
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


def send_whatsapp_interactive(
    recipient_phone: str,
    interactive_payload: dict,
    sender_user: str = "Assistant",
    db: Optional[Session] = None
) -> dict:
    """
    Sends a native WhatsApp interactive message (list menu or action buttons) via Meta Cloud API.
    """
    clean_phone = normalize_phone(recipient_phone)

    if not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        mock_id = f"sim_interactive_{int(datetime.utcnow().timestamp())}"
        return {"status": "success_simulated", "message_id": mock_id}

    url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone.replace("+", ""),
        "type": "interactive",
        "interactive": interactive_payload
    }

    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.post(url, headers=headers, json=payload)
            data = resp.json()
            if resp.status_code == 200:
                msg_id = data.get("messages", [{}])[0].get("id", "")
                return {"status": "success", "message_id": msg_id}
            else:
                err_msg = str(data.get("error", resp.text))
                logger.error(f"[Meta Interactive Send Error] {err_msg}")
                return {"status": "failed", "error": err_msg}
    except Exception as e:
        logger.error(f"[Meta Interactive Send Exception] {e}")
        return {"status": "error", "message": str(e)}


def upload_template_sample_to_meta(file_bytes: bytes, mime_type: str, filename: str) -> dict:
    """
    Uploads a template header sample file to Meta using the Resumable Upload API:
    1. POST /{APP_ID}/uploads -> get upload session ID
    2. POST /upload:{SESSION_ID} -> upload binary data and retrieve file handle 'h'
    Returns {"status": "success", "header_handle": "4:..."}
    """
    if not WHATSAPP_API_TOKEN or not getattr(config, "META_APP_ID", None):
        mock_handle = f"4:sim_handle_{int(datetime.utcnow().timestamp())}"
        return {"status": "success_simulated", "header_handle": mock_handle}

    app_id = config.META_APP_ID
    headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}"}
    params = {
        "file_length": len(file_bytes),
        "file_type": mime_type,
        "file_name": filename
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            # Step 1: Start upload session
            init_url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{app_id}/uploads"
            init_res = client.post(init_url, headers=headers, params=params)
            init_data = init_res.json()
            if init_res.status_code != 200 or "id" not in init_data:
                err = str(init_data.get("error", init_res.text))
                logger.error(f"[Meta Resumable Upload Init Error] {err}")
                return {"status": "failed", "error": err}

            upload_session_id = init_data["id"]

            # Step 2: Upload binary bytes to obtain handle 'h'
            binary_url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{upload_session_id}"
            binary_headers = {
                "Authorization": f"OAuth {WHATSAPP_API_TOKEN}",
                "file_offset": "0",
                "Content-Type": mime_type
            }
            bin_res = client.post(binary_url, headers=binary_headers, content=file_bytes)
            bin_data = bin_res.json()
            if bin_res.status_code == 200 and "h" in bin_data:
                return {"status": "success", "header_handle": bin_data["h"]}
            else:
                err = str(bin_data.get("error", bin_res.text))
                logger.error(f"[Meta Resumable Upload Binary Error] {err}")
                return {"status": "failed", "error": err}
    except Exception as e:
        logger.error(f"[Meta Resumable Upload Exception] {e}")
        return {"status": "error", "error": str(e)}


def upload_media_to_meta(file_bytes: bytes, mime_type: str, filename: str) -> dict:
    """
    Uploads a file directly to Meta's Cloud API media endpoint:
    POST /v19.0/{PHONE_NUMBER_ID}/media
    Returns {"status": "success", "media_id": "..."} or {"status": "failed", "error": "..."}.
    """
    if not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        mock_id = f"sim_media_{int(datetime.utcnow().timestamp())}"
        return {"status": "success_simulated", "media_id": mock_id}

    url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/media"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}"
    }
    files = {
        "file": (filename, file_bytes, mime_type)
    }
    data = {
        "messaging_product": "whatsapp"
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, data=data, files=files)
            resp_data = resp.json()
            if resp.status_code == 200 and "id" in resp_data:
                return {"status": "success", "media_id": resp_data["id"]}
            else:
                err_msg = str(resp_data.get("error", resp.text))
                logger.error(f"[Meta Media Upload Failed] {err_msg}")
                return {"status": "failed", "error": err_msg}
    except Exception as e:
        logger.error(f"[Meta Media Upload Exception] {e}")
        return {"status": "error", "error": str(e)}


def send_whatsapp_media(
    recipient_phone: str,
    media_type: str,  # "image", "document", "video", "audio"
    media_id: Optional[str] = None,
    media_url: Optional[str] = None,
    caption: Optional[str] = None,
    filename: Optional[str] = None,
    sender_user: str = "Agent",
    db: Optional[Session] = None
) -> dict:
    """
    Sends an outbound media message (document, image, video, audio) to a recipient via WhatsApp Cloud API.
    """
    owns_db = False
    if db is None:
        db = SessionLocal()
        owns_db = True
    try:
        is_auth, auth_reason = authorize_outbound_message(
            db=db,
            recipient_phone=recipient_phone,
            message_type=f"media_{media_type}",
            sender_user=sender_user
        )
        if not is_auth:
            logger.warning(f"[Policy Blocked] Media to {mask_phone(recipient_phone)} blocked: {auth_reason}")
            try:
                log_entry = models.MessageLog(
                    recipient_phone=recipient_phone,
                    template_name=f"media_{media_type}",
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

        if not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
            mock_id = f"sim_media_msg_{int(datetime.utcnow().timestamp())}"
            logger.info(f"[SIMULATED MEDIA CHAT] Agent sent {media_type} to {mask_phone(clean_phone)}: url={media_url}, id={media_id}")
            return {
                "status": "success_simulated",
                "message_id": mock_id,
                "info": "Simulated locally without live Meta credentials"
            }

        headers = {
            "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
            "Content-Type": "application/json"
        }

        # Build media object payload
        media_obj = {}
        if media_id:
            media_obj["id"] = media_id
        elif media_url:
            media_obj["link"] = media_url
        else:
            return {"status": "failed", "error": "Either media_id or media_url must be provided"}

        if caption and media_type in ["image", "video", "document"]:
            media_obj["caption"] = caption
        if filename and media_type == "document":
            media_obj["filename"] = filename

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_phone.replace("+", ""),
            "type": media_type,
            media_type: media_obj
        }

        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.post(META_API_URL, headers=headers, json=payload)
            data = resp.json()
            if resp.status_code == 200:
                msg_id = data.get("messages", [{}])[0].get("id", "")
                return {"status": "success", "message_id": msg_id}
            else:
                error_info = str(data.get("error", {}))
                logger.error(f"Meta media send error: {error_info}")
                return {"status": "failed", "error": error_info}
    except Exception as e:
        logger.error(f"Error in send_whatsapp_media: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if owns_db:
            db.close()


def send_whatsapp_reaction(
    recipient_phone: str,
    target_meta_message_id: str,
    emoji: str = "👍",
    db: Optional[Session] = None
) -> dict:
    """
    Sends a WhatsApp message reaction (e.g. 👍 or 👎) via Meta Cloud API.
    To remove a reaction, pass emoji="".
    """
    clean_phone = normalize_phone(recipient_phone)
    if not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        return {"status": "success_simulated", "message_id": f"sim_react_{int(datetime.utcnow().timestamp())}"}

    url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone.replace("+", ""),
        "type": "reaction",
        "reaction": {
            "message_id": target_meta_message_id,
            "emoji": emoji or ""
        }
    }

    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.post(url, headers=headers, json=payload)
            data = resp.json()
            if resp.status_code == 200:
                msg_id = data.get("messages", [{}])[0].get("id", "")
                return {"status": "success", "message_id": msg_id}
            else:
                err_msg = str(data.get("error", resp.text))
                logger.error(f"[Meta Reaction Error] {err_msg}")
                return {"status": "failed", "error": err_msg}
    except Exception as e:
        logger.error(f"[Meta Reaction Exception] {e}")
        return {"status": "error", "error": str(e)}


def download_meta_media(media_id: str, output_dir: str = "uploads") -> Optional[dict]:
    """
    Retrieves and downloads an inbound media attachment from Meta Cloud API by media_id.
    1. GET https://graph.facebook.com/v19.0/{media_id} -> returns url and mime_type
    2. GET {url} with Bearer token -> binary stream
    3. Saves file into output_dir and returns {filepath, filename, mime_type, relative_url}.
    """
    if not WHATSAPP_API_TOKEN or not media_id or media_id.startswith("sim_"):
        return None

    try:
        meta_url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{media_id}"
        headers = {"Authorization": f"Bearer {WHATSAPP_API_TOKEN}"}

        with httpx.Client(timeout=20.0) as client:
            meta_resp = client.get(meta_url, headers=headers)
            if meta_resp.status_code != 200:
                logger.error(f"[Media Download] Failed to fetch media info for {media_id}: {meta_resp.text}")
                return None
            meta_info = meta_resp.json()
            download_url = meta_info.get("url")
            mime_type = meta_info.get("mime_type", "application/octet-stream")

            if not download_url:
                return None

            dl_resp = client.get(download_url, headers=headers)
            if dl_resp.status_code != 200:
                logger.error(f"[Media Download] Failed to download binary for {media_id}: {dl_resp.status_code}")
                return None

            os.makedirs(output_dir, exist_ok=True)
            import mimetypes
            ext = mimetypes.guess_extension(mime_type) or ".bin"
            if ext == ".jpe":
                ext = ".jpg"
            saved_filename = f"{media_id}{ext}"
            saved_path = os.path.join(output_dir, saved_filename)

            with open(saved_path, "wb") as f:
                f.write(dl_resp.content)

            return {
                "filepath": saved_path,
                "filename": saved_filename,
                "mime_type": mime_type,
                "relative_url": f"/uploads/{saved_filename}"
            }
    except Exception as e:
        logger.error(f"[Media Download Exception] {e}")
        return None
