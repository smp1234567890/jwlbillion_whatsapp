import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
import config

logger = logging.getLogger("email_service")

SUPPORT_RECIPIENTS = ["ansbillion@gmail.com", "jwlbillion@gmail.com"]

def send_support_escalation_email(
    customer_phone: str,
    customer_name: Optional[str],
    latest_message: str,
    chat_history: Optional[str] = "",
    order_info: Optional[str] = None
) -> bool:
    """
    Sends an escalation email to ansbillion@gmail.com and jwlbillion@gmail.com
    when a customer asks for support or order tracking / shipment queries.
    """
    smtp_host = getattr(config, "SMTP_HOST", None) or getattr(config, "EMAIL_HOST", "smtp.gmail.com")
    smtp_port = int(getattr(config, "SMTP_PORT", None) or getattr(config, "EMAIL_PORT", 587))
    smtp_user = getattr(config, "SMTP_USER", None) or getattr(config, "EMAIL_HOST_USER", None)
    smtp_pass = getattr(config, "SMTP_PASSWORD", None) or getattr(config, "EMAIL_HOST_PASSWORD", None)

    subject = f"[Customer Support Escalation] WhatsApp Inquiry from {customer_name or customer_phone}"
    
    body = f"""Hello Support Team,

A customer on WhatsApp requires human customer support assistance.
AI auto-reply has been automatically paused for this customer so the support team can assist directly.

Customer Details:
- Phone: {customer_phone}
- Name: {customer_name or 'N/A'}
- Latest Customer Message: {latest_message}
"""
    if order_info:
        body += f"\nDetected Order Details:\n{order_info}\n"

    if chat_history:
        body += f"\nRecent WhatsApp Conversation:\n{'-'*40}\n{chat_history}\n{'-'*40}\n"

    body += "\nPlease review the Live Chat inbox on Scalifts CRM (https://jwlbillion.vercel.app) to respond to the customer."

    # If SMTP credentials are not configured, log clearly and return False gracefully
    if not smtp_user or not smtp_pass:
        logger.warning(
            f"[Email Notification] SMTP credentials not set (SMTP_USER/SMTP_PASSWORD). "
            f"Escalation logged for {customer_phone}. Set SMTP_USER and SMTP_PASSWORD in .env to enable direct dispatch."
        )
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = ", ".join(SUPPORT_RECIPIENTS)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, SUPPORT_RECIPIENTS, msg.as_string())

        logger.info(f"[Email Notification Sent] Escalated support chat for {customer_phone} to {SUPPORT_RECIPIENTS}")
        return True
    except Exception as e:
        logger.error(f"[Email Notification Error] Failed to send support escalation email: {e}")
        return False
