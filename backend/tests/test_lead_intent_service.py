import pytest
from datetime import datetime, timedelta
from services.lead_intent_service import analyze_conversation_interest

def test_client_initiated_pricing_highly_interested():
    now = datetime.utcnow()
    messages = [
        {
            "sender_type": "CUSTOMER",
            "text": "Hello, can you send me the price catalog for wholesale bulk order?",
            "created_at": now - timedelta(minutes=10)
        },
        {
            "sender_type": "AGENT",
            "text": "Sure, here is our current catalog.",
            "created_at": now - timedelta(minutes=8)
        },
        {
            "sender_type": "CUSTOMER",
            "text": "Thanks! How much discount on 500 units? Also what is delivery time to Delhi?",
            "created_at": now - timedelta(minutes=5)
        }
    ]
    result = analyze_conversation_interest(messages)
    assert result["is_client_initiated"] is True
    assert result["interest_level"] == "HIGHLY_INTERESTED"
    assert result["interest_score"] >= 70
    assert "price" in result["detected_signals"]
    assert "wholesale" in result["detected_signals"]
    assert result["inbound_count"] == 2

def test_client_initiated_general_interested():
    now = datetime.utcnow()
    messages = [
        {
            "sender_type": "CUSTOMER",
            "text": "Hi, where is your store located?",
            "created_at": now - timedelta(minutes=20)
        },
        {
            "sender_type": "AGENT",
            "text": "We are located at Connaught Place, New Delhi.",
            "created_at": now - timedelta(minutes=18)
        }
    ]
    result = analyze_conversation_interest(messages)
    assert result["is_client_initiated"] is True
    assert result["interest_level"] in ["INTERESTED", "HIGHLY_INTERESTED"]
    assert result["inbound_count"] == 1

def test_outbound_broadcast_no_reply():
    now = datetime.utcnow()
    messages = [
        {
            "sender_type": "AGENT",
            "text": "Flash Sale! 50% off on all items today only.",
            "created_at": now - timedelta(hours=2)
        }
    ]
    result = analyze_conversation_interest(messages)
    assert result["is_client_initiated"] is False
    assert result["interest_level"] == "OUTBOUND_ONLY"
    assert result["interest_score"] == 0
    assert result["inbound_count"] == 0

def test_client_opt_out_not_interested():
    now = datetime.utcnow()
    messages = [
        {
            "sender_type": "CUSTOMER",
            "text": "Stop sending messages, not interested.",
            "created_at": now - timedelta(minutes=5)
        }
    ]
    result = analyze_conversation_interest(messages)
    assert result["is_client_initiated"] is True
    assert result["interest_level"] == "NOT_INTERESTED"
    assert result["interest_score"] <= 10
