import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
import models
from services.policy_service import record_consent, revoke_consent, has_active_consent
from services.phone_service import normalize_phone


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_consent_lifecycle_grant_and_revoke(db):
    phone = "+919876543210"

    assert has_active_consent(db, phone) is False

    # Grant consent
    rec = record_consent(db, phone, source="store_checkout", proof_details="order:123")
    db.commit()

    assert rec.status == "ACTIVE"
    assert has_active_consent(db, phone) is True

    # Revoke consent
    revoke_consent(db, phone, reason="INBOUND_STOP_COMMAND")
    db.commit()

    assert has_active_consent(db, phone) is False
    opt_out = db.query(models.OptOut).filter(models.OptOut.phone == phone).first()
    assert opt_out is not None
    assert opt_out.reason == "INBOUND_STOP_COMMAND"


def test_re_granting_consent_after_revocation(db):
    phone = "+919876543210"

    record_consent(db, phone, source="store_checkout")
    revoke_consent(db, phone, reason="USER_REQUEST")
    db.commit()
    assert has_active_consent(db, phone) is False

    # Note: re-granting requires clearing opt-out if policy allows affirmative opt-in
    db.query(models.OptOut).filter(models.OptOut.phone == phone).delete()
    record_consent(db, phone, source="explicit_web_form")
    db.commit()

    assert has_active_consent(db, phone) is True
