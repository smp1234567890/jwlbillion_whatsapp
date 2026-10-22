"""add_quiet_hours_setting

Revision ID: bd2a3c4e5f6a
Revises: ac1f2e3d4b5c
Create Date: 2026-09-21 23:00:00.000000

Adds initial system_setting for quiet_hours_enabled defaulting to 'false' (testing mode).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = 'bd2a3c4e5f6a'
down_revision: Union[str, None] = 'ac1f2e3d4b5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = insp.get_table_names()

    if "system_settings" in tables:
        # Insert 'quiet_hours_enabled' = 'false' if not present
        existing = conn.execute(
            text("SELECT key FROM system_settings WHERE key = 'quiet_hours_enabled'")
        ).fetchone()
        if not existing:
            conn.execute(
                text("INSERT INTO system_settings (key, value) VALUES ('quiet_hours_enabled', 'false')")
            )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = insp.get_table_names()
    if "system_settings" in tables:
        conn.execute(text("DELETE FROM system_settings WHERE key = 'quiet_hours_enabled'"))
