"""initial_schema_baseline

Revision ID: 2a5d3eeb2bd6
Revises: 
Create Date: 2026-09-18 23:48:18.048627

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a5d3eeb2bd6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema safely without dropping legacy data."""
    # Ensure system_settings table and index exist
    try:
        op.create_index(op.f('ix_system_settings_key'), 'system_settings', ['key'], unique=False)
    except Exception:
        pass


def downgrade() -> None:
    """Downgrade schema."""
    try:
        op.drop_index(op.f('ix_system_settings_key'), table_name='system_settings')
    except Exception:
        pass
