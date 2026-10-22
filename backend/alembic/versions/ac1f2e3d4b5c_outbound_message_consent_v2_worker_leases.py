"""outbound_message_consent_v2_and_worker_leases

Revision ID: ac1f2e3d4b5c
Revises: 9c4e6f8a0b2d
Create Date: 2026-09-20 22:00:00.000000

WP2: Add outbound_messages table; extend consent_records with channel/policy_version.
WP5: Add partial unique index on message_logs.meta_message_id (WHERE NOT NULL).
WP8: Add claimed_by/claimed_until/attempt_count to workflow_sessions and campaigns.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'ac1f2e3d4b5c'
down_revision: Union[str, None] = '9c4e6f8a0b2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # ── WP2: outbound_messages ────────────────────────────────────────────────
    if "outbound_messages" not in existing_tables:
        op.create_table(
            "outbound_messages",
            sa.Column("id", sa.Integer, primary_key=True, index=True),
            sa.Column("idempotency_key", sa.String(200), unique=True, nullable=False),
            sa.Column("recipient_phone_e164", sa.String(20), nullable=False),
            sa.Column("recipient_hash", sa.String(64), nullable=False),
            sa.Column("message_kind", sa.String(20), nullable=False),
            sa.Column("purpose", sa.String(30), nullable=False),
            sa.Column("template_name", sa.String(100), nullable=True),
            sa.Column("campaign_id", sa.Integer, sa.ForeignKey("campaigns.id"), nullable=True),
            sa.Column("workflow_session_id", sa.Integer, sa.ForeignKey("workflow_sessions.id"), nullable=True),
            sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("service_actor", sa.String(50), nullable=True),
            sa.Column("policy_decision", sa.String(20), nullable=False, server_default="authorized"),
            sa.Column("policy_reason", sa.Text, nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("meta_message_id", sa.String(100), nullable=True),
            sa.Column("error_message", sa.Text, nullable=True),
            sa.Column("correlation_id", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("dispatched_at", sa.DateTime, nullable=True),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        )
        op.create_index("ix_outbound_messages_idempotency_key", "outbound_messages", ["idempotency_key"], unique=True)
        op.create_index("ix_outbound_messages_recipient_phone", "outbound_messages", ["recipient_phone_e164"])
        op.create_index("ix_outbound_messages_created_at", "outbound_messages", ["created_at"])

    # ── WP2: consent_records — add channel, policy_version, contact_id columns ─
    if "consent_records" in existing_tables:
        cr_cols = [c["name"] for c in insp.get_columns("consent_records")]
        with op.batch_alter_table("consent_records") as batch_op:
            if "channel" not in cr_cols:
                batch_op.add_column(
                    sa.Column("channel", sa.String(40), nullable=True, server_default="WHATSAPP_MARKETING")
                )
            if "policy_version" not in cr_cols:
                batch_op.add_column(
                    sa.Column("policy_version", sa.String(10), nullable=True, server_default="1.0")
                )
            if "contact_id" not in cr_cols:
                batch_op.add_column(
                    sa.Column("contact_id", sa.Integer, nullable=True)
                )
            if "evidence" not in cr_cols:
                batch_op.add_column(
                    sa.Column("evidence", sa.Text, nullable=True)
                )
        # Backfill: map ACTIVE → GRANTED in status column
        conn.execute(sa.text(
            "UPDATE consent_records SET status = 'GRANTED' WHERE status = 'ACTIVE'"
        ))
        conn.execute(sa.text(
            "UPDATE consent_records SET channel = 'WHATSAPP_MARKETING' WHERE channel IS NULL"
        ))
        conn.execute(sa.text(
            "UPDATE consent_records SET policy_version = '1.0' WHERE policy_version IS NULL"
        ))

    # ── WP5: partial unique index on message_logs.meta_message_id ────────────
    if "message_logs" in existing_tables:
        # Check if the partial unique index already exists
        try:
            # PostgreSQL supports WHERE in CREATE UNIQUE INDEX; safe to retry
            conn.execute(sa.text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_message_logs_meta_message_id
                ON message_logs (meta_message_id)
                WHERE meta_message_id IS NOT NULL
            """))
        except Exception:
            pass  # Index may already exist or dialect does not support partial index (SQLite dev)

    # ── WP8: workflow_sessions lease columns ──────────────────────────────────
    if "workflow_sessions" in existing_tables:
        ws_cols = [c["name"] for c in insp.get_columns("workflow_sessions")]
        with op.batch_alter_table("workflow_sessions") as batch_op:
            if "claimed_by" not in ws_cols:
                batch_op.add_column(sa.Column("claimed_by", sa.String(64), nullable=True))
            if "claimed_until" not in ws_cols:
                batch_op.add_column(sa.Column("claimed_until", sa.DateTime, nullable=True))
            if "attempt_count" not in ws_cols:
                batch_op.add_column(sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"))
        # Index for efficient un-claimed session queries
        try:
            op.create_index("ix_workflow_sessions_claimed_until", "workflow_sessions", ["claimed_until"])
        except Exception:
            pass

    # ── WP8: campaigns lease columns ──────────────────────────────────────────
    if "campaigns" in existing_tables:
        camp_cols = [c["name"] for c in insp.get_columns("campaigns")]
        with op.batch_alter_table("campaigns") as batch_op:
            if "claimed_by" not in camp_cols:
                batch_op.add_column(sa.Column("claimed_by", sa.String(64), nullable=True))
            if "claimed_until" not in camp_cols:
                batch_op.add_column(sa.Column("claimed_until", sa.DateTime, nullable=True))
            if "attempt_count" not in camp_cols:
                batch_op.add_column(sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # WP8 campaigns
    if "campaigns" in existing_tables:
        camp_cols = [c["name"] for c in insp.get_columns("campaigns")]
        with op.batch_alter_table("campaigns") as batch_op:
            for col in ("attempt_count", "claimed_until", "claimed_by"):
                if col in camp_cols:
                    batch_op.drop_column(col)

    # WP8 workflow_sessions
    if "workflow_sessions" in existing_tables:
        ws_cols = [c["name"] for c in insp.get_columns("workflow_sessions")]
        try:
            op.drop_index("ix_workflow_sessions_claimed_until", "workflow_sessions")
        except Exception:
            pass
        with op.batch_alter_table("workflow_sessions") as batch_op:
            for col in ("attempt_count", "claimed_until", "claimed_by"):
                if col in ws_cols:
                    batch_op.drop_column(col)

    # WP5 partial index
    try:
        conn.execute(sa.text("DROP INDEX IF EXISTS uq_message_logs_meta_message_id"))
    except Exception:
        pass

    # WP2 consent_records columns
    if "consent_records" in existing_tables:
        conn.execute(sa.text("UPDATE consent_records SET status = 'ACTIVE' WHERE status = 'GRANTED'"))
        cr_cols = [c["name"] for c in insp.get_columns("consent_records")]
        with op.batch_alter_table("consent_records") as batch_op:
            for col in ("evidence", "contact_id", "policy_version", "channel"):
                if col in cr_cols:
                    batch_op.drop_column(col)

    # WP2 outbound_messages
    if "outbound_messages" in existing_tables:
        op.drop_table("outbound_messages")
