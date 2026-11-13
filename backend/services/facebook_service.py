import logging
import requests
import config

logger = logging.getLogger("facebook_service")

GRAPH_API_VERSION = "v21.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def send_facebook_text_message(recipient_id: str, text: str) -> dict:
    """
    Sends a Messenger text reply to a customer via the Facebook Graph Send API.
    Uses the Page Access Token.
    """
    token = config.FACEBOOK_PAGE_ACCESS_TOKEN
    if not token:
        logger.error("[Facebook Messenger] FACEBOOK_PAGE_ACCESS_TOKEN is missing!")
        return {"status": "error", "error": "FACEBOOK_PAGE_ACCESS_TOKEN not configured"}

    url = f"{GRAPH_BASE_URL}/me/messages"
    params = {"access_token": token}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE"
    }

    try:
        resp = requests.post(url, params=params, json=payload, timeout=config.HTTP_TIMEOUT_SECONDS)
        data = resp.json()
        if resp.status_code == 200:
            msg_id = data.get("message_id")
            logger.info(f"[Facebook Messenger] Successfully sent message to {recipient_id}: {msg_id}")
            return {"status": "success", "message_id": msg_id}
        else:
            logger.error(f"[Facebook Messenger] Send error ({resp.status_code}): {data}")
            return {"status": "error", "error": data}
    except Exception as exc:
        logger.exception(f"[Facebook Messenger] Failed to dispatch message to {recipient_id}: {exc}")
        return {"status": "error", "error": str(exc)}

