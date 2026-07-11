"""Resume profiles (AI-parsed job applications)

Revision ID: 002
Revises: 001
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("emails.id"), nullable=False),
        sa.Column("attachment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_attachments.id")),
        sa.Column("candidate_name", sa.String(200)),
        sa.Column("candidate_email", sa.String(200)),
        sa.Column("candidate_phone", sa.String(50)),
        sa.Column("education", postgresql.JSONB, server_default="[]"),
        sa.Column("experience", postgresql.JSONB, server_default="[]"),
        sa.Column("skills", postgresql.JSONB, server_default="[]"),
        sa.Column("desired_position", sa.String(200)),
        sa.Column("expected_salary", sa.String(100)),
        sa.Column("years_experience", sa.Integer),
        sa.Column("summary", sa.Text),
        sa.Column("match_score", sa.SmallInteger),
        sa.Column("match_notes", sa.Text),
        sa.Column("llm_model", sa.String(100)),
        sa.Column("source", sa.String(20), server_default="attachment"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_resume_profiles_tenant_id", "resume_profiles", ["tenant_id"])
    op.create_index("ix_resume_profiles_email_id", "resume_profiles", ["email_id"])


def downgrade() -> None:
    op.drop_table("resume_profiles")
