import pytest
from datetime import datetime, timedelta
from database import SessionLocal
import models
from services.job_claim_service import claim_campaign, renew_campaign_lease, release_campaign

def test_renew_campaign_lease():
    db = SessionLocal()
    try:
        # Create a test campaign
        camp = models.Campaign(
            title="Test Lease Renewal",
            template_name="test_tmpl",
            target_filter="ALL",
            status="IN_PROGRESS",
            total_recipients=100
        )
        db.add(camp)
        db.commit()
        db.refresh(camp)

        worker_id = "test_worker_123"
        claimed = claim_campaign(db, camp.id, worker_id=worker_id, lease_seconds=60)
        assert claimed is True

        db.refresh(camp)
        assert camp.claimed_by == worker_id
        orig_until = camp.claimed_until

        # Renew lease
        renewed = renew_campaign_lease(db, camp.id, worker_id, lease_seconds=900)
        assert renewed is True

        db.refresh(camp)
        assert camp.claimed_until > orig_until

        # Non-matching worker cannot renew
        wrong_renew = renew_campaign_lease(db, camp.id, "wrong_worker", lease_seconds=900)
        assert wrong_renew is False

        # Cleanup
        release_campaign(db, camp.id)
        db.delete(camp)
        db.commit()
    finally:
        db.close()
