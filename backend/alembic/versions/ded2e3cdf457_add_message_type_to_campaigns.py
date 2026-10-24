"""add_message_type_to_campaigns

Revision ID: ded2e3cdf457
Revises: fa6e7f8a9b0c
Create Date: 2026-10-25 03:07:03.440549

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ded2e3cdf457'
down_revision: Union[str, Sequence[str], None] = 'fa6e7f8a9b0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: safely add message_type to campaigns if it doesn't already exist."""
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'campaigns' AND column_name = 'message_type'
            ) THEN
                ALTER TABLE campaigns ADD COLUMN message_type VARCHAR(20) NOT NULL DEFAULT 'marketing';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('campaigns', 'message_type')
