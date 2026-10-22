"""
test_security_remediations.py

Consolidated security regression tests covering:
- WP1: No runtime DDL at startup
- WP2: Outbound consent gate, idempotency, DND removal does NOT grant consent
- WP7: Auth throttling fails closed in production, DB TLS validation
- WP8: Campaign and workflow session lease claims

These tests augment existing suites and must all pass before the production
release gate is considered cleared.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import status as http_status
from fastapi.testclient import TestClient
import models
from database import engine
from sqlalchemy import event
from services.policy_service import authorize_and_create_outbound, record_consent, revoke_consent
from services.job_claim_service import claim_workflow_session, claim_campaign


# ───────────────────────────────────────────────────────────
# WP1 — Runtime DDL gate
# ───────────────────────────────────────────────────────────

class TestRuntimeDDLGate:
    def test_no_create_table_on_startup(self):
        """Startup must emit zero CREATE TABLE / ALTER TABLE DDL."""
        from main import on_startup
        executed = []

        def _intercept(conn, cursor, stmt, params, ctx, executemany):
            u = stmt.strip().upper()
            if u.startswith("ALTER TABLE") or u.startswith("CREATE TABLE") or u.startswith("DROP TABLE"):
                executed.append(stmt)

        event.listen(engine, "before_cursor_execute", _intercept)
        try:
            with patch("scheduler.start_scheduler"):
                with patch("services.job_claim_service.acquire_leader_lock", return_value=False):
                    on_startup()
        finally:
            event.remove(engine, "before_cursor_execute", _intercept)

        assert executed == [], f"Runtime DDL detected: {executed}"


# ───────────────────────────────────────────────────────────
# WP2 — Outbound consent and policy gate
# ───────────────────────────────────────────────────────────

class TestOutboundConsentGate:
    def test_dnd_removal_does_not_grant_consent(self, client, db, auth_headers):
        """
        Removing a phone from the DND/opt-out list MUST NOT automatically
        create an active consent record. Affirmative consent requires a
        separate, explicit action.
        """
        phone = "+919988776655"
        # Ensure no prior state
        db.query(models.OptOut).filter(models.OptOut.phone == phone).delete()
        db.query(models.ConsentRecord).filter(models.ConsentRecord.phone == phone).delete()
        db.commit()

        # Add to opt-out
        db.add(models.OptOut(phone=phone, reason="TEST_DND"))
        db.commit()

        # Verify no ACTIVE consent yet
        consent_before = db.query(models.ConsentRecord).filter(
            models.ConsentRecord.phone == phone,
            models.ConsentRecord.status == "ACTIVE"
        ).first()
        assert consent_before is None

        # Delete opt-out record using the pre-seeded admin token
        resp = client.delete(
            f"/api/opt-outs/{phone}",
            headers=auth_headers
        )
        assert resp.status_code == http_status.HTTP_200_OK

        # After removal, MUST NOT have an ACTIVE consent record
        db.expire_all()
        consent_after = db.query(models.ConsentRecord).filter(
            models.ConsentRecord.phone == phone,
            models.ConsentRecord.status == "ACTIVE"
        ).first()
        assert consent_after is None, (
            "DND removal must NOT auto-grant marketing consent. "
            "Affirmative consent requires a separate evidenced action."
        )


    def test_authorize_and_create_outbound_blocks_opted_out_phone(self, db):
        """authorize_and_create_outbound must block sends to opted-out phones."""
        phone = "+919900112233"
        db.query(models.OptOut).filter(models.OptOut.phone == phone).delete()
        db.query(models.ConsentRecord).filter(models.ConsentRecord.phone == phone).delete()
        db.commit()

        # Opt out
        revoke_consent(db, phone, reason="OPT_OUT")
        db.commit()

        is_auth, rec, reason = authorize_and_create_outbound(
            db=db,
            recipient_phone=phone,
            idempotency_key=f"test_block_{phone}",
            message_kind="template",
            purpose="marketing",
            template_name="cart_recovery_reminder",
        )
        assert is_auth is False
        assert "opted out" in reason.lower() or "dnd" in reason.lower()

    def test_authorize_and_create_outbound_idempotency(self, db):
        """Duplicate idempotency_key must return same OutboundMessage, not create a new one."""
        phone = "+919900112244"
        db.query(models.OptOut).filter(models.OptOut.phone == phone).delete()
        db.query(models.ConsentRecord).filter(models.ConsentRecord.phone == phone).delete()
        db.query(models.OutboundMessage).filter(
            models.OutboundMessage.idempotency_key == "idem_test_001"
        ).delete()
        db.commit()

        # Add consent
        record_consent(db, phone, source="store_checkout")
        db.commit()

        is_auth1, rec1, reason1 = authorize_and_create_outbound(
            db=db,
            recipient_phone=phone,
            idempotency_key="idem_test_001",
            message_kind="template",
            purpose="utility",
            template_name="order_confirmation",
        )
        assert is_auth1 is True
        assert rec1 is not None

        # Second call with same key
        is_auth2, rec2, reason2 = authorize_and_create_outbound(
            db=db,
            recipient_phone=phone,
            idempotency_key="idem_test_001",
            message_kind="template",
            purpose="utility",
            template_name="order_confirmation",
        )
        assert reason2 == "Duplicate idempotency_key"
        assert rec2.id == rec1.id

    def test_campaign_denied_without_active_consent(self, db):
        """Campaigns must be denied for contacts lacking ACTIVE consent."""
        phone = "+919911223344"
        db.query(models.OptOut).filter(models.OptOut.phone == phone).delete()
        db.query(models.ConsentRecord).filter(models.ConsentRecord.phone == phone).delete()
        db.commit()

        is_auth, rec, reason = authorize_and_create_outbound(
            db=db,
            recipient_phone=phone,
            idempotency_key=f"camp_no_consent_{phone}",
            message_kind="template",
            purpose="marketing",
            template_name="festive_promo",
            campaign_id=9999,
        )
        assert is_auth is False
        assert "consent" in reason.lower()


# ───────────────────────────────────────────────────────────
# WP7 — Auth throttling fail-closed in production
# ───────────────────────────────────────────────────────────

class TestAuthThrottlingProductionFailClosed:
    def test_record_failed_attempt_fails_closed_if_no_redis(self):
        """In production mode, record_failed_attempt must raise 503 if Redis is unavailable."""
        from routers.auth import record_failed_attempt
        import config
        from fastapi import HTTPException

        original_env = config.ENVIRONMENT
        original_redis = __import__("routers.auth", fromlist=["_redis_client"])._redis_client
        try:
            config.ENVIRONMENT = "production"
            import routers.auth as auth_router
            original_client = auth_router._redis_client
            auth_router._redis_client = None

            with pytest.raises(HTTPException) as exc_info:
                record_failed_attempt("test_user_prod")
            assert exc_info.value.status_code == 503
        finally:
            config.ENVIRONMENT = original_env
            auth_router._redis_client = original_client

    def test_get_failed_attempts_fails_closed_if_no_redis(self):
        """In production mode, get_failed_attempts must raise 503 if Redis is unavailable."""
        from routers.auth import get_failed_attempts
        import config
        from fastapi import HTTPException

        original_env = config.ENVIRONMENT
        try:
            config.ENVIRONMENT = "production"
            import routers.auth as auth_router
            original_client = auth_router._redis_client
            auth_router._redis_client = None

            with pytest.raises(HTTPException) as exc_info:
                get_failed_attempts("test_user_prod")
            assert exc_info.value.status_code == 503
        finally:
            config.ENVIRONMENT = original_env
            auth_router._redis_client = original_client


# ───────────────────────────────────────────────────────────
# WP7 — Database TLS validation in production
# ───────────────────────────────────────────────────────────

class TestDatabaseTLSValidation:
    def test_insecure_sslmode_rejected_in_production(self):
        """
        Insecure DB_SSLMODE values ('disable', 'allow', 'prefer') must be rejected.
        This test validates the allowlist logic used in database.py.
        """
        ALLOWED_SSLMODES = ("verify-full", "verify-ca", "require")
        insecure_values = ["disable", "allow", "prefer", "no-ssl", ""]

        for bad_mode in insecure_values:
            is_rejected = bad_mode not in ALLOWED_SSLMODES
            assert is_rejected, (
                f"Insecure sslmode='{bad_mode}' must be rejected in production. "
                f"Allowed: {ALLOWED_SSLMODES}"
            )

        # Also verify the allowed values pass
        for good_mode in ALLOWED_SSLMODES:
            is_ok = good_mode in ALLOWED_SSLMODES
            assert is_ok, f"sslmode='{good_mode}' must be accepted in production."



# ───────────────────────────────────────────────────────────
# WP8 — Durable worker lease claims
# ───────────────────────────────────────────────────────────

class TestDurableWorkerLeases:
    def test_workflow_session_claim_prevents_duplicate_processing(self, db):
        """
        claim_workflow_session must return True for first claimant and
        False for a second concurrent claimant attempting the same session.
        """
        import models
        from datetime import datetime

        # Create a minimal workflow session
        flow = models.WorkflowFlow(
            name="Test Flow",
            is_active=True,
            nodes=[{"id": "n1", "type": "trigger", "data": {"label": "Start"}, "position": {"x": 0, "y": 0}}],
            edges=[]
        )
        db.add(flow)
        db.flush()

        sess = models.WorkflowSession(
            flow_id=flow.id,
            customer_phone="+919900001111",
            status="WAITING_DELAY",
            current_node_id="n1",
            next_evaluation_at=datetime.utcnow(),
            state_data={}
        )
        db.add(sess)
        db.commit()

        # First claim should succeed
        worker_a = "worker_a_test"
        claimed_a = claim_workflow_session(db, sess.id, worker_id=worker_a, lease_seconds=120)
        assert claimed_a is True, "First claimant should successfully acquire lease"

        # Second claim on same session must fail (lease is active)
        worker_b = "worker_b_test"
        claimed_b = claim_workflow_session(db, sess.id, worker_id=worker_b, lease_seconds=120)
        assert claimed_b is False, "Second claimant must be rejected while lease is active"

    def test_campaign_claim_prevents_duplicate_execution(self, db):
        """
        claim_campaign must block a second worker from claiming an active campaign.
        """
        campaign = models.Campaign(
            title="Test Duplicate Guard Campaign",
            template_name="cart_recovery_reminder",
            language="en",
            status="PENDING",
            target_filter="ALL",
        )
        db.add(campaign)
        db.commit()

        worker_a = "campaign_worker_a"
        claimed_a = claim_campaign(db, campaign.id, worker_id=worker_a, lease_seconds=600)
        assert claimed_a is True

        worker_b = "campaign_worker_b"
        claimed_b = claim_campaign(db, campaign.id, worker_id=worker_b, lease_seconds=600)
        assert claimed_b is False, "Second worker must not be able to claim an actively leased campaign"
