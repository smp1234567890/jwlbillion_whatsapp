"""add_carousel_cards_to_templates

Revision ID: 1b2c3d4e5f6a
Revises: f2a3b4c5d6e7
Create Date: 2026-11-12 23:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1b2c3d4e5f6a'
down_revision: Union[str, Sequence[str], None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Safely add carousel_cards JSON column to templates table."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'templates' AND column_name = 'carousel_cards'
                ) THEN
                    ALTER TABLE templates ADD COLUMN carousel_cards JSON NULL;
                END IF;
            END $$;
            """
        )
    else:
        with op.batch_alter_table('templates') as batch_op:
            batch_op.add_column(sa.Column('carousel_cards', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('templates') as batch_op:
        batch_op.drop_column('carousel_cards')
