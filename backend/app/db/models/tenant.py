import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(20), default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    # settings keys: llm_config (enc), summary_config, default_tone

    users: Mapped[list["User"]] = relationship("User", back_populates="tenant", lazy="raise")
    departments: Mapped[list["Department"]] = relationship("Department", back_populates="tenant", lazy="raise")
    email_accounts: Mapped[list["EmailAccount"]] = relationship("EmailAccount", back_populates="tenant", lazy="raise")
    sensitive_words: Mapped[list["SensitiveWord"]] = relationship("SensitiveWord", back_populates="tenant", lazy="raise")


class Department(Base, TimestampMixin):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="departments", lazy="raise")
