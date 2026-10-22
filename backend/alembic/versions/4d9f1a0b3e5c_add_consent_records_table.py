"""add_consent_records_table

Revision ID: 4d9f1a0b3e5c
Revises: 3c8e9f1a0b2d
Create Date: 2026-09-20 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d9f1a0b3e5c'
down_revision: Union[str, Sequence[str], None] = '3c8e9f1a0b2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    if 'consent_records' not in tables:
        op.create_table(
            'consent_records',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('phone', sa.String(length=20), nullable=False),
            sa.Column('source', sa.String(length=50), nullable=False, server_default='store_checkout'),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='ACTIVE'),
            sa.Column('proof_details', sa.Text(), nullable=True),
            sa.Column('consent_timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
        )
        op.create_index('ix_consent_records_phone', 'consent_records', ['phone'], unique=False)
        op.create_index('ix_consent_records_status', 'consent_records', ['status'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    if 'consent_records' in tables:
        op.drop_index('ix_consent_records_status', table_name='consent_records')
        op.drop_index('ix_consent_records_phone', table_name='consent_records')
        op.drop_table('consent_records')
