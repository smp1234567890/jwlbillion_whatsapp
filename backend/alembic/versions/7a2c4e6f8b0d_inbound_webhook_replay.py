"""inbound webhook replay protection and batch tracking

Revision ID: 7a2c4e6f8b0d
Revises: 6f1b3c2d5e7a
Create Date: 2026-09-20 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a2c4e6f8b0d'
down_revision: Union[str, None] = '6f1b3c2d5e7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if "inbound_webhook_events" not in existing_tables:
        op.create_table(
            "inbound_webhook_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("provider_event_id", sa.String(length=128), nullable=False),
            sa.Column("event_type", sa.String(length=50), nullable=True),
            sa.Column("payload_hash", sa.String(length=64), nullable=True),
            sa.Column("correlation_id", sa.String(length=64), nullable=True),
            sa.Column("processed_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "provider_event_id", name="uq_inbound_provider_event")
        )
        op.create_index("ix_inbound_webhook_events_provider", "inbound_webhook_events", ["provider"])
        op.create_index("ix_inbound_webhook_events_provider_event_id", "inbound_webhook_events", ["provider_event_id"])

    # Ensure unique index on chat_messages.meta_message_id if chat_messages exists
    if "chat_messages" in existing_tables:
        indexes = [idx["name"] for idx in insp.get_indexes("chat_messages")]
        if "uq_chat_messages_meta_message_id" not in indexes:
            try:
                conn.execute(sa.text("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_messages_meta_message_id
                    ON chat_messages (meta_message_id)
                    WHERE meta_message_id IS NOT NULL AND meta_message_id != ''
                """))
            except Exception:
                pass


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if "chat_messages" in existing_tables:
        indexes = [idx["name"] for idx in insp.get_indexes("chat_messages")]
        if "uq_chat_messages_meta_message_id" in indexes:
            try:
                op.drop_index("uq_chat_messages_meta_message_id", table_name="chat_messages")
            except Exception:
                pass

    if "inbound_webhook_events" in existing_tables:
        op.drop_table("inbound_webhook_events")
