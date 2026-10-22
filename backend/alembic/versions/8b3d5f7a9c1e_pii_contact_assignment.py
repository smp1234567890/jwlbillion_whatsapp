"""pii contact assignment and support send capability

Revision ID: 8b3d5f7a9c1e
Revises: 7a2c4e6f8b0d
Create Date: 2026-09-20 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b3d5f7a9c1e'
down_revision: Union[str, None] = '7a2c4e6f8b0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = insp.get_table_names()

    # 1. contacts.assigned_user_id
    if "contacts" in tables:
        contacts_cols = [c["name"] for c in insp.get_columns("contacts")]
        with op.batch_alter_table("contacts", schema=None) as batch_op:
            if "assigned_user_id" not in contacts_cols:
                batch_op.add_column(
                    sa.Column("assigned_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True)
                )
                try:
                    batch_op.create_index("ix_contacts_assigned_user_id", ["assigned_user_id"], unique=False)
                except Exception:
                    pass

    # 2. chat_messages.assigned_user_id
    if "chat_messages" in tables:
        chat_cols = [c["name"] for c in insp.get_columns("chat_messages")]
        with op.batch_alter_table("chat_messages", schema=None) as batch_op:
            if "assigned_user_id" not in chat_cols:
                batch_op.add_column(
                    sa.Column("assigned_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True)
                )
                try:
                    batch_op.create_index("ix_chat_messages_assigned_user_id", ["assigned_user_id"], unique=False)
                except Exception:
                    pass

    # 3. users.can_support_send
    if "users" in tables:
        users_cols = [c["name"] for c in insp.get_columns("users")]
        with op.batch_alter_table("users", schema=None) as batch_op:
            if "can_support_send" not in users_cols:
                batch_op.add_column(
                    sa.Column("can_support_send", sa.Boolean(), server_default=sa.text("false"), nullable=False)
                )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    tables = insp.get_table_names()

    # 1. users.can_support_send
    if "users" in tables:
        users_cols = [c["name"] for c in insp.get_columns("users")]
        with op.batch_alter_table("users", schema=None) as batch_op:
            if "can_support_send" in users_cols:
                batch_op.drop_column("can_support_send")

    # 2. chat_messages.assigned_user_id
    if "chat_messages" in tables:
        chat_cols = [c["name"] for c in insp.get_columns("chat_messages")]
        with op.batch_alter_table("chat_messages", schema=None) as batch_op:
            if "assigned_user_id" in chat_cols:
                try:
                    batch_op.drop_index("ix_chat_messages_assigned_user_id")
                except Exception:
                    pass
                batch_op.drop_column("assigned_user_id")

    # 3. contacts.assigned_user_id
    if "contacts" in tables:
        contacts_cols = [c["name"] for c in insp.get_columns("contacts")]
        with op.batch_alter_table("contacts", schema=None) as batch_op:
            if "assigned_user_id" in contacts_cols:
                try:
                    batch_op.drop_index("ix_contacts_assigned_user_id")
                except Exception:
                    pass
                batch_op.drop_column("assigned_user_id")
