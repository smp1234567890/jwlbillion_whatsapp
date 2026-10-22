"""reconcile_runtime_schema_to_alembic

Revision ID: cf3b4d5e6a7b
Revises: bd2a3c4e5f6a
Create Date: 2026-09-22 00:00:00.000000

WP1: Reconcile all runtime schema definitions and custom columns into Alembic migrations
so the application requires ZERO runtime DDL at startup.
- contacts: custom_attributes JSON
- automation_rules: approval_status, pending_recipients_count, total_triggered, created_at, variable_mappings, expires_at
- users: totp_secret, totp_enabled, is_2fa_enabled, email_recovery_code, email_recovery_code_expires, recovery_email, role, auth_version, can_support_send
- contacts: city, tags, is_vip, order_count, last_order_date, assigned_user_id, birth_day, birth_month
- campaigns: claimed_by, claimed_until, attempt_count
- chat_messages: assigned_user_id
- templates: variable_mappings
- cart_events: extra_data, authenticated_user
- message_logs: campaign_id, sender_user
- webhook_events: source, external_event_id, idempotency_key, hmac_validated, correlation_id, received_at
- workflow_sessions: claimed_by, claimed_until, attempt_count
- tables: system_settings, external_data_sources, integration_secrets, audit_events
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'cf3b4d5e6a7b'
down_revision: Union[str, None] = 'bd2a3c4e5f6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = set(insp.get_table_names())

    # ── 1. system_settings ────────────────────────────────────────────────────
    if "system_settings" not in existing_tables:
        op.create_table(
            "system_settings",
            sa.Column("key", sa.String(50), primary_key=True),
            sa.Column("value", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        )
        existing_tables.add("system_settings")

    # ── 2. external_data_sources ──────────────────────────────────────────────
    if "external_data_sources" not in existing_tables:
        op.create_table(
            "external_data_sources",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("endpoint_url", sa.Text(), nullable=False),
            sa.Column("auth_method", sa.String(30), server_default="bearer"),
            sa.Column("secret_reference", sa.String(100), nullable=True),
            sa.Column("approved_hostname", sa.String(255), nullable=True),
            sa.Column("purpose", sa.String(100), server_default="customer_lookup"),
            sa.Column("lookup_param", sa.String(30), server_default="phone"),
            sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        existing_tables.add("external_data_sources")

    # ── 3. integration_secrets ────────────────────────────────────────────────
    if "integration_secrets" not in existing_tables:
        op.create_table(
            "integration_secrets",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("secret_reference", sa.String(100), unique=True, nullable=False),
            sa.Column("encrypted_value", sa.Text(), nullable=False),
            sa.Column("nonce", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )
        existing_tables.add("integration_secrets")

    # ── 4. audit_events ───────────────────────────────────────────────────────
    if "audit_events" not in existing_tables:
        op.create_table(
            "audit_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("target_type", sa.String(100), nullable=True),
            sa.Column("target_id", sa.String(100), nullable=True),
            sa.Column("correlation_id", sa.String(64), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        existing_tables.add("audit_events")

    # ── 4b. system_migrations ─────────────────────────────────────────────────
    if "system_migrations" not in existing_tables:
        op.create_table(
            "system_migrations",
            sa.Column("migration_name", sa.String(120), primary_key=True),
            sa.Column("applied_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        )
        existing_tables.add("system_migrations")

    # ── Helper for idempotent column additions ────────────────────────────────
    def add_column_if_missing(table_name: str, col_name: str, col_type, **kwargs):
        if table_name not in existing_tables:
            return
        cols = [c["name"] for c in insp.get_columns(table_name)]
        if col_name not in cols:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.add_column(sa.Column(col_name, col_type, **kwargs))

    # ── 5. contacts columns ───────────────────────────────────────────────────
    add_column_if_missing("contacts", "city", sa.String(100))
    add_column_if_missing("contacts", "tags", sa.String(500))
    add_column_if_missing("contacts", "is_vip", sa.Boolean(), server_default=sa.false())
    add_column_if_missing("contacts", "order_count", sa.Integer(), server_default="0")
    add_column_if_missing("contacts", "last_order_date", sa.DateTime())
    add_column_if_missing("contacts", "assigned_user_id", sa.Integer())
    add_column_if_missing("contacts", "birth_day", sa.Integer())
    add_column_if_missing("contacts", "birth_month", sa.Integer())
    add_column_if_missing("contacts", "custom_attributes", sa.JSON(), server_default="{}")

    # ── 6. users columns ──────────────────────────────────────────────────────
    add_column_if_missing("users", "totp_secret", sa.String(64))
    add_column_if_missing("users", "totp_enabled", sa.Boolean(), server_default=sa.false())
    add_column_if_missing("users", "is_2fa_enabled", sa.Boolean(), server_default=sa.false())
    add_column_if_missing("users", "email_recovery_code", sa.String(10))
    add_column_if_missing("users", "email_recovery_code_expires", sa.DateTime())
    add_column_if_missing("users", "recovery_email", sa.String(200))
    add_column_if_missing("users", "role", sa.String(20), server_default="agent")
    add_column_if_missing("users", "auth_version", sa.Integer(), server_default="1")
    add_column_if_missing("users", "can_support_send", sa.Boolean(), server_default=sa.false())

    # ── 7. automation_rules columns ───────────────────────────────────────────
    add_column_if_missing("automation_rules", "approval_status", sa.String(50), server_default="IDLE")
    add_column_if_missing("automation_rules", "pending_recipients_count", sa.Integer(), server_default="0")
    add_column_if_missing("automation_rules", "total_triggered", sa.Integer(), server_default="0")
    add_column_if_missing("automation_rules", "created_at", sa.DateTime(), server_default=sa.func.now())
    add_column_if_missing("automation_rules", "variable_mappings", sa.JSON())
    add_column_if_missing("automation_rules", "expires_at", sa.DateTime())

    # ── 8. campaigns columns ──────────────────────────────────────────────────
    add_column_if_missing("campaigns", "claimed_by", sa.String(64))
    add_column_if_missing("campaigns", "claimed_until", sa.DateTime())
    add_column_if_missing("campaigns", "attempt_count", sa.Integer(), server_default="0")

    # ── 9. workflow_sessions columns ──────────────────────────────────────────
    add_column_if_missing("workflow_sessions", "claimed_by", sa.String(64))
    add_column_if_missing("workflow_sessions", "claimed_until", sa.DateTime())
    add_column_if_missing("workflow_sessions", "attempt_count", sa.Integer(), server_default="0")

    # ── 10. chat_messages columns ─────────────────────────────────────────────
    add_column_if_missing("chat_messages", "assigned_user_id", sa.Integer())

    # ── 11. templates columns ─────────────────────────────────────────────────
    add_column_if_missing("templates", "variable_mappings", sa.JSON())

    # ── 12. cart_events columns ───────────────────────────────────────────────
    add_column_if_missing("cart_events", "extra_data", sa.JSON())
    add_column_if_missing("cart_events", "authenticated_user", sa.String(50))

    # ── 13. message_logs columns ──────────────────────────────────────────────
    add_column_if_missing("message_logs", "campaign_id", sa.Integer())
    add_column_if_missing("message_logs", "sender_user", sa.String(50), server_default="System")

    # ── 14. webhook_events columns ────────────────────────────────────────────
    add_column_if_missing("webhook_events", "source", sa.String(50), server_default="store")
    add_column_if_missing("webhook_events", "external_event_id", sa.String(150))
    add_column_if_missing("webhook_events", "idempotency_key", sa.String(150))
    add_column_if_missing("webhook_events", "hmac_validated", sa.Boolean(), server_default=sa.false())
    add_column_if_missing("webhook_events", "correlation_id", sa.String(64))
    add_column_if_missing("webhook_events", "received_at", sa.DateTime(), server_default=sa.func.now())


def downgrade() -> None:
    pass
