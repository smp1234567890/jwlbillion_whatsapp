import pytest
from unittest.mock import patch
from sqlalchemy import event
from database import engine, get_db
import config
import main
from main import on_startup


def test_startup_and_api_operations_emit_zero_runtime_ddl(client, auth_headers):
    """
    WP1 Security Audit Verification:
    Asserts that application startup and runtime operations emit ZERO DDL statements
    (CREATE TABLE, ALTER TABLE, DROP TABLE, TRUNCATE).
    All database migrations must strictly be managed via Alembic.
    """
    ddl_statements = []

    def ddl_listener(conn, cursor, statement, parameters, context, executemany):
        s = statement.strip().upper()
        if any(s.startswith(prefix) for prefix in ["CREATE TABLE", "ALTER TABLE", "DROP TABLE", "TRUNCATE"]):
            ddl_statements.append(statement)

    event.listen(engine, "before_cursor_execute", ddl_listener)
    try:
        # 1. Startup hook must not emit any DDL
        with patch("scheduler.start_scheduler"):
            with patch("services.job_claim_service.acquire_leader_lock", return_value=False):
                on_startup()

        # 2. Inbound customer sync must not emit any DDL
        sync_payload = {
            "phone": "+919988776655",
            "name": "DDL Audit User",
            "custom_role": "Tester"
        }
        res = client.post("/api/contacts/sync", json=sync_payload, headers={"X-API-Key": config.WEBHOOK_SECRET})
        assert res.status_code in [200, 201]

        # 3. System setting checks must not emit any DDL
        db = next(get_db())
        try:
            import models
            setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "daily_limit").first()
            assert setting is not None
            assert setting.value == "200"
        finally:
            db.close()

    finally:
        event.remove(engine, "before_cursor_execute", ddl_listener)

    assert len(ddl_statements) == 0, f"Disallowed runtime DDL statement(s) detected: {ddl_statements}"
