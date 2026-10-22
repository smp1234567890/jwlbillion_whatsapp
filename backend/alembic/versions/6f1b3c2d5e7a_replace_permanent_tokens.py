"""replace permanent tokens with auth_version and refresh_tokens

Revision ID: 6f1b3c2d5e7a
Revises: 5e0a2b1c4f6d
Create Date: 2026-09-20 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f1b3c2d5e7a'
down_revision: Union[str, None] = '5e0a2b1c4f6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # 1. Create refresh_tokens table
    if 'refresh_tokens' not in existing_tables:
        op.create_table(
            'refresh_tokens',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('token_hash', sa.String(length=64), nullable=False),
            sa.Column('family_id', sa.String(length=64), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('rotated_at', sa.DateTime(), nullable=True),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_refresh_tokens_id'), 'refresh_tokens', ['id'], unique=False)
        op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
        op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=True)
        op.create_index(op.f('ix_refresh_tokens_family_id'), 'refresh_tokens', ['family_id'], unique=False)

    # 2. Update users table with auth_version and drop permanent api_token
    if 'users' in existing_tables:
        existing_cols = [c['name'] for c in insp.get_columns('users')]
        with op.batch_alter_table('users', schema=None) as batch_op:
            if 'auth_version' not in existing_cols:
                batch_op.add_column(sa.Column('auth_version', sa.Integer(), nullable=False, server_default='1'))
            if 'api_token' in existing_cols:
                batch_op.drop_column('api_token')
            if 'api_token_created_at' in existing_cols:
                batch_op.drop_column('api_token_created_at')


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'users' in existing_tables:
        existing_cols = [c['name'] for c in insp.get_columns('users')]
        with op.batch_alter_table('users', schema=None) as batch_op:
            if 'api_token' not in existing_cols:
                batch_op.add_column(sa.Column('api_token', sa.String(length=128), nullable=True))
            if 'api_token_created_at' not in existing_cols:
                batch_op.add_column(sa.Column('api_token_created_at', sa.DateTime(), nullable=True))
            if 'auth_version' in existing_cols:
                batch_op.drop_column('auth_version')

    if 'refresh_tokens' in existing_tables:
        op.drop_index(op.f('ix_refresh_tokens_family_id'), table_name='refresh_tokens')
        op.drop_index(op.f('ix_refresh_tokens_token_hash'), table_name='refresh_tokens')
        op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
        op.drop_index(op.f('ix_refresh_tokens_id'), table_name='refresh_tokens')
        op.drop_table('refresh_tokens')
