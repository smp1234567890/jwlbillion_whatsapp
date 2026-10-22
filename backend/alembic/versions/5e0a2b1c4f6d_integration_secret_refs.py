"""add integration secret refs and audit events

Revision ID: 5e0a2b1c4f6d
Revises: 4d9f1a0b3e5c
Create Date: 2026-09-20 20:07:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5e0a2b1c4f6d'
down_revision: Union[str, None] = '4d9f1a0b3e5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # 1. Create integration_secrets table
    if 'integration_secrets' not in existing_tables:
        op.create_table(
            'integration_secrets',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('secret_reference', sa.String(length=100), nullable=False),
            sa.Column('encrypted_value', sa.Text(), nullable=False),
            sa.Column('nonce', sa.String(length=64), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_integration_secrets_id'), 'integration_secrets', ['id'], unique=False)
        op.create_index(op.f('ix_integration_secrets_secret_reference'), 'integration_secrets', ['secret_reference'], unique=True)

    # 2. Create audit_events table
    if 'audit_events' not in existing_tables:
        op.create_table(
            'audit_events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('actor_user_id', sa.Integer(), nullable=True),
            sa.Column('action', sa.String(length=100), nullable=False),
            sa.Column('target_type', sa.String(length=100), nullable=True),
            sa.Column('target_id', sa.String(length=100), nullable=True),
            sa.Column('correlation_id', sa.String(length=64), nullable=True),
            sa.Column('metadata_json', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_audit_events_id'), 'audit_events', ['id'], unique=False)
        op.create_index(op.f('ix_audit_events_actor_user_id'), 'audit_events', ['actor_user_id'], unique=False)
        op.create_index(op.f('ix_audit_events_action'), 'audit_events', ['action'], unique=False)
        op.create_index(op.f('ix_audit_events_correlation_id'), 'audit_events', ['correlation_id'], unique=False)

    # 3. Create or alter external_data_sources table
    if 'external_data_sources' not in existing_tables:
        op.create_table(
            'external_data_sources',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('endpoint_url', sa.Text(), nullable=False),
            sa.Column('auth_method', sa.String(length=30), nullable=True, server_default='bearer'),
            sa.Column('secret_reference', sa.String(length=100), nullable=True),
            sa.Column('approved_hostname', sa.String(length=255), nullable=True),
            sa.Column('purpose', sa.String(length=100), nullable=True, server_default='customer_lookup'),
            sa.Column('lookup_param', sa.String(length=30), nullable=True, server_default='phone'),
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_external_data_sources_id'), 'external_data_sources', ['id'], unique=False)
    else:
        existing_cols = [c['name'] for c in insp.get_columns('external_data_sources')]
        with op.batch_alter_table('external_data_sources', schema=None) as batch_op:
            if 'secret_reference' not in existing_cols:
                batch_op.add_column(sa.Column('secret_reference', sa.String(length=100), nullable=True))
            if 'approved_hostname' not in existing_cols:
                batch_op.add_column(sa.Column('approved_hostname', sa.String(length=255), nullable=True))
            if 'purpose' not in existing_cols:
                batch_op.add_column(sa.Column('purpose', sa.String(length=100), nullable=True, server_default='customer_lookup'))
            if 'api_key' in existing_cols:
                batch_op.drop_column('api_key')
            if 'header_name' in existing_cols:
                batch_op.drop_column('header_name')


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'external_data_sources' in existing_tables:
        existing_cols = [c['name'] for c in insp.get_columns('external_data_sources')]
        with op.batch_alter_table('external_data_sources', schema=None) as batch_op:
            if 'header_name' not in existing_cols:
                batch_op.add_column(sa.Column('header_name', sa.String(length=100), nullable=True, server_default='X-CRM-Token'))
            if 'api_key' not in existing_cols:
                batch_op.add_column(sa.Column('api_key', sa.Text(), nullable=True))
            if 'purpose' in existing_cols:
                batch_op.drop_column('purpose')
            if 'approved_hostname' in existing_cols:
                batch_op.drop_column('approved_hostname')
            if 'secret_reference' in existing_cols:
                batch_op.drop_column('secret_reference')

    if 'audit_events' in existing_tables:
        op.drop_index(op.f('ix_audit_events_correlation_id'), table_name='audit_events')
        op.drop_index(op.f('ix_audit_events_action'), table_name='audit_events')
        op.drop_index(op.f('ix_audit_events_actor_user_id'), table_name='audit_events')
        op.drop_index(op.f('ix_audit_events_id'), table_name='audit_events')
        op.drop_table('audit_events')

    if 'integration_secrets' in existing_tables:
        op.drop_index(op.f('ix_integration_secrets_secret_reference'), table_name='integration_secrets')
        op.drop_index(op.f('ix_integration_secrets_id'), table_name='integration_secrets')
        op.drop_table('integration_secrets')
