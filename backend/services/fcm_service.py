import logging
import os
from typing import List, Optional
from sqlalchemy.orm import Session
import models

logger = logging.getLogger("fcm_service")

_firebase_initialized = False

def init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return True
    try:
        import firebase_admin
        from firebase_admin import credentials

        # Check for service account key file
        key_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-adminsdk.json")
        if not os.path.exists(key_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            alt_path = os.path.join(base_dir, "firebase-adminsdk.json")
            if os.path.exists(alt_path):
                key_path = alt_path

        if os.path.exists(key_path):
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase Admin initialized successfully with service account.")
            return True
        else:
            logger.warning(f"Firebase credentials not found at {key_path}. Push notifications disabled.")
            return False
    except ValueError:
        # Already initialized
        _firebase_initialized = True
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin: {e}")
        return False


def register_device_token(db: Session, token: str, user_id: Optional[int] = None, platform: str = "android"):
    """Saves or refreshes an FCM device token in the database."""
    try:
        existing = db.query(models.DeviceToken).filter(models.DeviceToken.token == token).first()
        if existing:
            if user_id:
                existing.user_id = user_id
            existing.platform = platform
        else:
            new_dev = models.DeviceToken(
                token=token,
                user_id=user_id,
                platform=platform
            )
            db.add(new_dev)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to register device token: {e}")
        return False


def send_chat_push_notification(db: Session, customer_name: str, message_text: str, customer_phone: str):
    """
    Sends a high-priority FCM notification to all active registered agent devices.
    Wakes up Android phones out of Deep Doze mode immediately.
    """
    if not init_firebase():
        return 0

    try:
        from firebase_admin import messaging

        tokens = [row[0] for row in db.query(models.DeviceToken.token).all() if row[0]]
        if not tokens:
            return 0

        # Construct High-Priority Android Notification
        android_config = messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                title=customer_name or customer_phone,
                body=message_text or "Sent a message",
                icon="ic_launcher",
                color="#064e3b",
                sound="notification",
                channel_id="jwl_incoming_messages_v3",
                click_action="FLUTTER_NOTIFICATION_CLICK"
            ),
            data={
                "chat_phone": customer_phone,
                "customer_name": customer_name or customer_phone,
                "message": message_text or "",
                "click_action": "OPEN_CHAT"
            }
        )

        sent_count = 0
        dead_tokens = []

        for fcm_token in tokens:
            message = messaging.Message(
                token=fcm_token,
                notification=messaging.Notification(
                    title=customer_name or customer_phone,
                    body=message_text or "Sent a message"
                ),
                data={
                    "chat_phone": customer_phone,
                    "customer_name": customer_name or customer_phone
                },
                android=android_config
            )
            try:
                messaging.send(message)
                sent_count += 1
            except messaging.UnregisteredError:
                # Token is dead, remove it from DB
                dead_tokens.append(fcm_token)
            except Exception as e:
                logger.warning(f"Error sending FCM push to token {fcm_token[:15]}...: {e}")

        if dead_tokens:
            try:
                db.query(models.DeviceToken).filter(models.DeviceToken.token.in_(dead_tokens)).delete(synchronize_session=False)
                db.commit()
            except Exception:
                db.rollback()

        logger.info(f"FCM push notification sent to {sent_count} device(s) for customer {customer_phone}")
        return sent_count
    except Exception as e:
        logger.error(f"FCM broadcast error: {e}", exc_info=True)
        return 0
