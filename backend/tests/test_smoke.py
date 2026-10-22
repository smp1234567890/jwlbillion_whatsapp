import sys
import os

# Ensure backend directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import SessionLocal, engine
import models
import whatsapp_service


def test_database_connection():
    db = SessionLocal()
    try:
        count = db.query(models.MessageLog).count()
        assert count >= 0
        print(f"✅ [Smoke Test] Database connection OK ({count} message logs found)")
    finally:
        db.close()


def test_system_settings():
    db = SessionLocal()
    try:
        limit = whatsapp_service.get_effective_daily_limit(db)
        assert limit > 0
        print(f"✅ [Smoke Test] System settings & daily limit OK (effective limit: {limit})")
    finally:
        db.close()


def test_chat_messages_query():
    db = SessionLocal()
    try:
        msgs = db.query(models.ChatMessage).limit(5).all()
        assert msgs is not None
        print(f"✅ [Smoke Test] Chat messages query OK ({len(msgs)} sample messages retrieved)")
    finally:
        db.close()


def test_campaigns_query():
    db = SessionLocal()
    try:
        camps = db.query(models.Campaign).limit(5).all()
        assert camps is not None
        print(f"✅ [Smoke Test] Campaigns query OK ({len(camps)} sample campaigns retrieved)")
    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 Running WhatsApp CRM Smoke Test Suite...")
    test_database_connection()
    test_system_settings()
    test_chat_messages_query()
    test_campaigns_query()
    print("🎉 All core smoke tests PASSED!")
