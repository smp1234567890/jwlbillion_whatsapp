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
    """Upgrade schema safely by ensuring base tables exist on a clean database."""
    conn = op.get_bind()
    import sys, os
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    import models
    from database import Base
    Base.metadata.create_all(bind=conn, checkfirst=True)

    insp = sa.inspect(conn)
    if "system_settings" in insp.get_table_names():
        indexes = [idx["name"] for idx in insp.get_indexes("system_settings")]
        if op.f("ix_system_settings_key") not in indexes:
            op.create_index(op.f("ix_system_settings_key"), "system_settings", ["key"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    try:
        op.drop_index(op.f('ix_system_settings_key'), table_name='system_settings')
    except Exception:
        pass
