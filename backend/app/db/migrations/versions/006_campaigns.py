"""Outbound campaigns + recipients (proactive send / SOP follow-ups)

Revision ID: 006
Revises: 005
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_accounts.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("subject_template", sa.String(500), nullable=False),
        sa.Column("body_template", sa.Text, nullable=False),
        sa.Column("sop_steps", sa.Integer, server_default="1"),
        sa.Column("sop_interval_hours", sa.Integer, server_default="72"),
        sa.Column("tone", sa.String(20), server_default="business"),
        sa.Column("language", sa.String(10), server_default="zh"),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_campaigns_tenant_id", "campaigns", ["tenant_id"])

    op.create_table(
        "campaign_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("current_step", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("last_sent_at", sa.DateTime(timezone=True)),
        sa.Column("next_send_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_campaign_recipients_tenant_id", "campaign_recipients", ["tenant_id"])
    op.create_index("ix_campaign_recipients_campaign_id", "campaign_recipients", ["campaign_id"])


def downgrade() -> None:
    op.drop_table("campaign_recipients")
    op.drop_table("campaigns")
