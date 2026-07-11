"""Customer profiles (aggregated correspondent档案)

Revision ID: 004
Revises: 003
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("company", sa.String(200)),
        sa.Column("email_count", sa.Integer, server_default="0"),
        sa.Column("first_seen", sa.DateTime(timezone=True)),
        sa.Column("last_seen", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("importance", sa.SmallInteger, server_default="1"),
        sa.Column("tags", postgresql.JSONB, server_default="[]"),
        sa.Column("summary", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "email", name="uq_customer_profiles_tenant_id_email"),
    )
    op.create_index("ix_customer_profiles_tenant_id", "customer_profiles", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("customer_profiles")
