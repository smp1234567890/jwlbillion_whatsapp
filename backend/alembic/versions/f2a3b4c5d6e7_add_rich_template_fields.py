"""add_rich_template_fields

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-10-30 17:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Safely add rich template fields to templates table (PostgreSQL & SQLite compatible)."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'templates' AND column_name = 'sub_type'
                ) THEN
                    ALTER TABLE templates ADD COLUMN sub_type VARCHAR(50) DEFAULT 'DEFAULT';
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'templates' AND column_name = 'header_type'
                ) THEN
                    ALTER TABLE templates ADD COLUMN header_type VARCHAR(20) DEFAULT 'NONE';
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'templates' AND column_name = 'buttons'
                ) THEN
                    ALTER TABLE templates ADD COLUMN buttons JSON NULL;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'templates' AND column_name = 'sample_values'
                ) THEN
                    ALTER TABLE templates ADD COLUMN sample_values JSON NULL;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'templates' AND column_name = 'validity_period_minutes'
                ) THEN
                    ALTER TABLE templates ADD COLUMN validity_period_minutes INTEGER NULL;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'templates' AND column_name = 'auth_config'
                ) THEN
                    ALTER TABLE templates ADD COLUMN auth_config JSON NULL;
                END IF;
            END $$;
            """
        )
    else:
        # SQLite / Dev fallback
        with op.batch_alter_table('templates') as batch_op:
            batch_op.add_column(sa.Column('sub_type', sa.String(50), server_default='DEFAULT', nullable=True))
            batch_op.add_column(sa.Column('header_type', sa.String(20), server_default='NONE', nullable=True))
            batch_op.add_column(sa.Column('buttons', sa.JSON(), nullable=True))
            batch_op.add_column(sa.Column('sample_values', sa.JSON(), nullable=True))
            batch_op.add_column(sa.Column('validity_period_minutes', sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column('auth_config', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('templates') as batch_op:
        batch_op.drop_column('auth_config')
        batch_op.drop_column('validity_period_minutes')
        batch_op.drop_column('sample_values')
        batch_op.drop_column('buttons')
        batch_op.drop_column('header_type')
        batch_op.drop_column('sub_type')

