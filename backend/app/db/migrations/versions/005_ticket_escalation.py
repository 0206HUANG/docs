"""Ticket escalation fields

Revision ID: 005
Revises: 004
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("escalation_level", sa.SmallInteger, server_default="0"))
    op.add_column("tickets", sa.Column("last_escalated_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("tickets", "last_escalated_at")
    op.drop_column("tickets", "escalation_level")
