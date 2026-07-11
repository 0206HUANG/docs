import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Campaign(Base, TimestampMixin):
    """An outbound campaign: a template sent to recipients with SOP follow-ups."""
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("email_accounts.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_template: Mapped[str] = mapped_column(String(500), nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    sop_steps: Mapped[int] = mapped_column(Integer, default=1)          # total sends incl. first
    sop_interval_hours: Mapped[int] = mapped_column(Integer, default=72)  # gap between sends
    tone: Mapped[str] = mapped_column(String(20), default="business")
    language: Mapped[str] = mapped_column(String(10), default="zh")
    status: Mapped[str] = mapped_column(String(20), default="draft")     # draft/running/paused/completed

    recipients: Mapped[list["CampaignRecipient"]] = relationship(
        "CampaignRecipient", back_populates="campaign", lazy="raise"
    )


class CampaignRecipient(Base, TimestampMixin):
    """One target of a campaign, tracked through its SOP follow-up sequence."""
    __tablename__ = "campaign_recipients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    current_step: Mapped[int] = mapped_column(Integer, default=0)        # sends already made
    status: Mapped[str] = mapped_column(String(20), default="pending")   # pending/sent/replied/completed/failed
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="recipients", lazy="raise")
