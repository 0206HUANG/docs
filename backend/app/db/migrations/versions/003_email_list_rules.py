"""Email list rules (sender black/white lists)

Revision ID: 003
Revises: 002
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_list_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("list_type", sa.String(10), nullable=False),
        sa.Column("match_type", sa.String(10), server_default="email"),
        sa.Column("value", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(200)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_email_list_rules_tenant_id", "email_list_rules", ["tenant_id"])
    op.create_index("ix_email_list_rules_lookup", "email_list_rules", ["tenant_id", "list_type", "value"])


def downgrade() -> None:
    op.drop_table("email_list_rules")
