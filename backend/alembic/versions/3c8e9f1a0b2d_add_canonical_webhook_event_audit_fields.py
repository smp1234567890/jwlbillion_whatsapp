"""add_canonical_webhook_event_audit_fields

Revision ID: 3c8e9f1a0b2d
Revises: 2a5d3eeb2bd6
Create Date: 2026-09-20 19:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c8e9f1a0b2d'
down_revision: Union[str, Sequence[str], None] = '2a5d3eeb2bd6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    if 'webhook_events' not in tables:
        # Fresh database — create table with all columns up-front
        op.create_table(
            'webhook_events',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('source', sa.String(length=50), nullable=True, server_default='store'),
            sa.Column('event_type', sa.String(length=50), nullable=False),
            sa.Column('external_event_id', sa.String(length=150), nullable=True),
            sa.Column('idempotency_key', sa.String(length=150), nullable=True),
            sa.Column('hmac_validated', sa.Boolean(), nullable=True, server_default='false'),
            sa.Column('correlation_id', sa.String(length=64), nullable=True),
            sa.Column('received_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
    else:
        # Table already exists — use ADD COLUMN IF NOT EXISTS (PostgreSQL-native, no table recreation)
        # batch_alter_table MUST NOT be used here; it tries to recreate the table on PostgreSQL
        # which fails when existing rows violate NOT NULL constraints.
        for ddl in [
            "ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'store'",
            "ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS external_event_id VARCHAR(150)",
            "ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(150)",
            "ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS hmac_validated BOOLEAN DEFAULT false",
            "ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS correlation_id VARCHAR(64)",
            "ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS received_at TIMESTAMP DEFAULT NOW()",
        ]:
            try:
                op.execute(sa.text(ddl))
            except Exception as e:
                # Log and continue — failure on one column must not abort the rest
                import logging
                logging.getLogger("alembic.3c8e9f1a0b2d").warning(f"Column migration note: {e}")

    # Create indexes idempotently
    try:
        insp2 = sa.inspect(bind)
        existing_indexes = {i['name'] for i in insp2.get_indexes('webhook_events')}
    except Exception:
        existing_indexes = set()

    for idx_name, col in [
        ('ix_webhook_events_source', 'source'),
        ('ix_webhook_events_external_event_id', 'external_event_id'),
        ('ix_webhook_events_correlation_id', 'correlation_id'),
    ]:
        if idx_name not in existing_indexes:
            try:
                op.create_index(idx_name, 'webhook_events', [col], unique=False)
            except Exception:
                pass


def downgrade() -> None:
    for idx in ('ix_webhook_events_correlation_id', 'ix_webhook_events_external_event_id', 'ix_webhook_events_source'):
        try:
            op.drop_index(idx, table_name='webhook_events')
        except Exception:
            pass
    for col in ('received_at', 'correlation_id', 'hmac_validated', 'idempotency_key', 'external_event_id', 'source'):
        try:
            op.drop_column('webhook_events', col)
        except Exception:
            pass
