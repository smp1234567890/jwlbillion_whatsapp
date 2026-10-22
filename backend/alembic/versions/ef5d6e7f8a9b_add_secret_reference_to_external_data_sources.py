"""add secret_reference column to external_data_sources if missing

Revision ID: ef5d6e7f8a9b
Revises: de4c5e6f7a8b
Create Date: 2026-09-24 00:00:00.000000

Production hotfix: The external_data_sources table on Aiven was created
before the secret_reference column was added to the SQLAlchemy model.
This causes:
  psycopg2.errors.UndefinedColumn: column external_data_sources.secret_reference does not exist
on every GET /api/external-data-sources request, wasting a DB connection
and causing the UI to always show an empty external data sources list.

This migration idempotently adds the column if it does not already exist.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'ef5d6e7f8a9b'
down_revision: Union[str, None] = 'de4c5e6f7a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = set(insp.get_table_names())

    if 'external_data_sources' not in existing_tables:
        # Table doesn't exist at all — create it with all required columns
        op.create_table(
            'external_data_sources',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('endpoint_url', sa.Text(), nullable=False),
            sa.Column('auth_method', sa.String(30), server_default='bearer'),
            sa.Column('secret_reference', sa.String(100), nullable=True),
            sa.Column('approved_hostname', sa.String(255), nullable=True),
            sa.Column('purpose', sa.String(100), server_default='customer_lookup'),
            sa.Column('lookup_param', sa.String(30), server_default='phone'),
            sa.Column('is_active', sa.Boolean(), server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
    else:
        # Table exists — add any missing columns idempotently
        existing_cols = [c['name'] for c in insp.get_columns('external_data_sources')]
        with op.batch_alter_table('external_data_sources', schema=None) as batch_op:
            if 'secret_reference' not in existing_cols:
                batch_op.add_column(sa.Column('secret_reference', sa.String(100), nullable=True))
            if 'approved_hostname' not in existing_cols:
                batch_op.add_column(sa.Column('approved_hostname', sa.String(255), nullable=True))
            if 'purpose' not in existing_cols:
                batch_op.add_column(sa.Column('purpose', sa.String(100), nullable=True, server_default='customer_lookup'))
            if 'lookup_param' not in existing_cols:
                batch_op.add_column(sa.Column('lookup_param', sa.String(30), nullable=True, server_default='phone'))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = set(insp.get_table_names())

    if 'external_data_sources' in existing_tables:
        existing_cols = [c['name'] for c in insp.get_columns('external_data_sources')]
        with op.batch_alter_table('external_data_sources', schema=None) as batch_op:
            if 'secret_reference' in existing_cols:
                batch_op.drop_column('secret_reference')
