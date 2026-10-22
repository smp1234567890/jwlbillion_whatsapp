import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
import models
from services.job_claim_service import (
    acquire_leader_lock,
    release_leader_lock,
    claim_workflow_session,
    generate_worker_id,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_worker_id_generation():
    w1 = generate_worker_id()
    w2 = generate_worker_id()
    assert w1 != w2
    assert len(w1) > 8


def test_leader_lock_sqlite_dev_fallback(db):
    """Verifies that in SQLite / dev environments, advisory lock falls back gracefully."""
    is_leader = acquire_leader_lock(db)
    assert is_leader is True
    # Release does not error
    release_leader_lock(db)


def test_claim_workflow_session_leasing(db):
    session = models.WorkflowSession(
        flow_id=1,
        customer_phone="+919876543210",
        status="ACTIVE"
    )
    db.add(session)
    db.commit()

    worker_a = "worker-host-a"
    worker_b = "worker-host-b"

    # Worker A claims session
    claimed_a = claim_workflow_session(db, session.id, worker_a, lease_seconds=60)
    assert claimed_a is True

    # Worker B tries to claim while lease is active
    claimed_b = claim_workflow_session(db, session.id, worker_b, lease_seconds=60)
    assert claimed_b is False

    # Verify session fields in DB
    db.refresh(session)
    assert session.claimed_by == worker_a
    assert session.attempt_count == 1
