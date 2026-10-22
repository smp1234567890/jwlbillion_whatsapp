"""backfill_consent_records

Revision ID: de4c5e6f7a8b
Revises: cf3b4d5e6a7b
Create Date: 2026-09-23 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'de4c5e6f7a8b'
down_revision: Union[str, None] = 'cf3b4d5e6a7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = set(insp.get_table_names())

    if 'contacts' in tables and 'consent_records' in tables:
        has_opt_outs = 'opt_outs' in tables
        if has_opt_outs:
            conn.execute(sa.text("""
                INSERT INTO consent_records (phone, source, status, proof_details, consent_timestamp, created_at)
                SELECT c.phone,
                       'store_sync_backfill',
                       'ACTIVE',
                       'Pre-consent-ledger active contact — backfilled from store integration',
                       CURRENT_TIMESTAMP,
                       CURRENT_TIMESTAMP
                FROM contacts c
                WHERE (c.is_active = TRUE OR c.is_active IS NULL)
                  AND NOT EXISTS (
                    SELECT 1 FROM consent_records cr WHERE cr.phone = c.phone AND cr.status = 'ACTIVE'
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM opt_outs oo WHERE oo.phone = c.phone
                  )
            """))
        else:
            conn.execute(sa.text("""
                INSERT INTO consent_records (phone, source, status, proof_details, consent_timestamp, created_at)
                SELECT c.phone,
                       'store_sync_backfill',
                       'ACTIVE',
                       'Pre-consent-ledger active contact — backfilled from store integration',
                       CURRENT_TIMESTAMP,
                       CURRENT_TIMESTAMP
                FROM contacts c
                WHERE (c.is_active = TRUE OR c.is_active IS NULL)
                  AND NOT EXISTS (
                    SELECT 1 FROM consent_records cr WHERE cr.phone = c.phone AND cr.status = 'ACTIVE'
                  )
            """))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = set(insp.get_table_names())

    if 'consent_records' in tables:
        conn.execute(sa.text("""
            DELETE FROM consent_records WHERE source = 'store_sync_backfill'
        """))
