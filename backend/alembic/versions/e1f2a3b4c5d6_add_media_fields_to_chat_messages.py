"""add_media_fields_to_chat_messages

Revision ID: e1f2a3b4c5d6
Revises: ded2e3cdf457
Create Date: 2026-10-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'ded2e3cdf457'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: safely add media_url and filename columns to chat_messages."""
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'chat_messages' AND column_name = 'media_url'
            ) THEN
                ALTER TABLE chat_messages ADD COLUMN media_url VARCHAR(1000) NULL;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'chat_messages' AND column_name = 'filename'
            ) THEN
                ALTER TABLE chat_messages ADD COLUMN filename VARCHAR(255) NULL;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chat_messages', 'filename')
    op.drop_column('chat_messages', 'media_url')
