"""add performance indexes for chat_messages, message_logs, workflow_sessions, and contacts

Revision ID: fa6e7f8a9b0c
Revises: ef5d6e7f8a9b
Create Date: 2026-10-24 00:00:00.000000

Adds indexes to high-frequency query columns:
- chat_messages: sender_type, is_read, created_at
- message_logs: status
- workflow_sessions: status
- contacts: created_at
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'fa6e7f8a9b0c'
down_revision: Union[str, None] = 'ef5d6e7f8a9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    def _index_exists(table_name: str, index_name: str) -> bool:
        if table_name not in insp.get_table_names():
            return False
        existing_indices = [idx['name'] for idx in insp.get_indexes(table_name)]
        return index_name in existing_indices

    # chat_messages indexes
    if not _index_exists('chat_messages', 'ix_chat_messages_sender_type'):
        op.create_index('ix_chat_messages_sender_type', 'chat_messages', ['sender_type'])
    if not _index_exists('chat_messages', 'ix_chat_messages_is_read'):
        op.create_index('ix_chat_messages_is_read', 'chat_messages', ['is_read'])
    if not _index_exists('chat_messages', 'ix_chat_messages_created_at'):
        op.create_index('ix_chat_messages_created_at', 'chat_messages', ['created_at'])

    # message_logs status index
    if not _index_exists('message_logs', 'ix_message_logs_status'):
        op.create_index('ix_message_logs_status', 'message_logs', ['status'])

    # workflow_sessions status index
    if not _index_exists('workflow_sessions', 'ix_workflow_sessions_status'):
        op.create_index('ix_workflow_sessions_status', 'workflow_sessions', ['status'])

    # contacts created_at index
    if not _index_exists('contacts', 'ix_contacts_created_at'):
        op.create_index('ix_contacts_created_at', 'contacts', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_contacts_created_at', table_name='contacts')
    op.drop_index('ix_workflow_sessions_status', table_name='workflow_sessions')
    op.drop_index('ix_message_logs_status', table_name='message_logs')
    op.drop_index('ix_chat_messages_created_at', table_name='chat_messages')
    op.drop_index('ix_chat_messages_is_read', table_name='chat_messages')
    op.drop_index('ix_chat_messages_sender_type', table_name='chat_messages')
