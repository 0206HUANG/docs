"""Email soft-delete flag

Revision ID: 008
Revises: 007
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("emails", sa.Column("is_deleted", sa.Boolean, server_default="false"))
    op.create_index("ix_emails_is_deleted", "emails", ["tenant_id", "is_deleted"])


def downgrade() -> None:
    op.drop_index("ix_emails_is_deleted", "emails")
    op.drop_column("emails", "is_deleted")
