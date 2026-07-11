"""Scheduled emails (定时发送) with open tracking

Revision ID: 007
Revises: 006
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduled_emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_accounts.id"), nullable=False),
        sa.Column("to_addrs", postgresql.JSONB, server_default="[]"),
        sa.Column("cc_addrs", postgresql.JSONB, server_default="[]"),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_text", sa.Text, nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("error_msg", sa.Text),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("track_opens", sa.Boolean, server_default="false"),
        sa.Column("tracking_id", postgresql.UUID(as_uuid=True), unique=True),
        sa.Column("open_count", sa.Integer, server_default="0"),
        sa.Column("first_opened_at", sa.DateTime(timezone=True)),
        sa.Column("last_opened_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scheduled_emails_tenant_id", "scheduled_emails", ["tenant_id"])
    op.create_index("ix_scheduled_emails_due", "scheduled_emails", ["status", "scheduled_at"])


def downgrade() -> None:
    op.drop_table("scheduled_emails")
