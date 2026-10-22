import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import event


def test_no_ddl_on_app_startup():
    """
    WP1 Verification: Ensure that starting the FastAPI application or running startup hooks
    does NOT execute any DDL statements (ALTER TABLE, CREATE TABLE, DROP TABLE) at runtime.
    All schema definitions must be strictly managed by Alembic migrations.
    """
    from database import engine, get_db
    import main
    from main import on_startup

    executed_ddl_statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        stmt_upper = statement.strip().upper()
        if stmt_upper.startswith("ALTER TABLE") or stmt_upper.startswith("CREATE TABLE") or stmt_upper.startswith("DROP TABLE"):
            executed_ddl_statements.append(statement)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        # Trigger startup hook with mocked scheduler to prevent background thread
        with patch("scheduler.start_scheduler"):
            with patch("services.job_claim_service.acquire_leader_lock", return_value=False):
                on_startup()
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

    assert len(executed_ddl_statements) == 0, f"Runtime DDL detected during application startup: {executed_ddl_statements}"
