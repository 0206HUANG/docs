import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class EmailAccount(Base, TimestampMixin):
    __tablename__ = "email_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"))
    email_address: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50), default="generic")
    imap_host: Mapped[str] = mapped_column(String(200), nullable=False)
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    imap_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    smtp_host: Mapped[str] = mapped_column(String(200), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, default=465)
    smtp_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    username: Mapped[str] = mapped_column(String(200), nullable=False)
    password_enc: Mapped[str] = mapped_column(Text, nullable=False)
    positioning: Mapped[str] = mapped_column(String(50), default="general")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_status: Mapped[str] = mapped_column(String(20), default="idle")
    error_message: Mapped[str | None] = mapped_column(Text)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="email_accounts", lazy="raise")
    emails: Mapped[list["Email"]] = relationship("Email", back_populates="account", lazy="raise")
    threads: Mapped[list["EmailThread"]] = relationship("EmailThread", back_populates="account", lazy="raise")


class EmailThread(Base):
    __tablename__ = "email_threads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("email_accounts.id"), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(500))
    participants: Mapped[list] = mapped_column(JSONB, default=list)
    last_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="open")

    account: Mapped["EmailAccount"] = relationship("EmailAccount", back_populates="threads", lazy="raise")
    emails: Mapped[list["Email"]] = relationship("Email", back_populates="thread", lazy="raise")


class Email(Base, TimestampMixin):
    __tablename__ = "emails"
    __table_args__ = (UniqueConstraint("message_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("email_accounts.id"), nullable=False)
    thread_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("email_threads.id"))
    message_id: Mapped[str] = mapped_column(String(500), nullable=False)
    in_reply_to: Mapped[str | None] = mapped_column(String(500))
    references: Mapped[str | None] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(String(10), default="inbound")
    from_addr: Mapped[str] = mapped_column(String(500), nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(200))
    to_addrs: Mapped[list] = mapped_column(JSONB, default=list)
    cc_addrs: Mapped[list] = mapped_column(JSONB, default=list)
    subject: Mapped[str | None] = mapped_column(String(500))
    body_text: Mapped[str | None] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(10))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    account: Mapped["EmailAccount"] = relationship("EmailAccount", back_populates="emails", lazy="raise")
    thread: Mapped["EmailThread | None"] = relationship("EmailThread", back_populates="emails", lazy="raise")
    classification: Mapped["EmailClassification | None"] = relationship("EmailClassification", back_populates="email", uselist=False, lazy="raise")
    reply: Mapped["EmailReply | None"] = relationship("EmailReply", back_populates="email", uselist=False, lazy="raise")
    attachments: Mapped[list["EmailAttachment"]] = relationship("EmailAttachment", back_populates="email", lazy="raise")
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="email", lazy="raise")


class EmailAttachment(Base, TimestampMixin):
    __tablename__ = "email_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emails.id"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_path: Mapped[str | None] = mapped_column(Text)

    email: Mapped["Email"] = relationship("Email", back_populates="attachments", lazy="raise")


class EmailClassification(Base):
    __tablename__ = "email_classifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emails.id"), unique=True, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    email_type: Mapped[str] = mapped_column(String(50), nullable=False)
    language: Mapped[str | None] = mapped_column(String(10))
    urgency: Mapped[int] = mapped_column(SmallInteger, default=1)
    has_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    sensitive_words: Mapped[list] = mapped_column(JSONB, default=list)
    confidence: Mapped[float | None]
    llm_model: Mapped[str | None] = mapped_column(String(100))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    email: Mapped["Email"] = relationship("Email", back_populates="classification", lazy="raise")


class EmailReply(Base, TimestampMixin):
    __tablename__ = "email_replies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emails.id"), unique=True, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    draft_content: Mapped[str | None] = mapped_column(Text)
    final_content: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending_review")
    send_strategy: Mapped[str] = mapped_column(String(20), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    llm_model: Mapped[str | None] = mapped_column(String(100))
    rag_chunk_ids: Mapped[list] = mapped_column(JSONB, default=list)
    attached_asset_ids: Mapped[list] = mapped_column(JSONB, default=list)

    email: Mapped["Email"] = relationship("Email", back_populates="reply", lazy="raise")


class ResumeProfile(Base, TimestampMixin):
    """Structured resume data extracted by AI from a job-application email."""
    __tablename__ = "resume_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    email_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("emails.id"), nullable=False)
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("email_attachments.id"))
    candidate_name: Mapped[str | None] = mapped_column(String(200))
    candidate_email: Mapped[str | None] = mapped_column(String(200))
    candidate_phone: Mapped[str | None] = mapped_column(String(50))
    education: Mapped[list] = mapped_column(JSONB, default=list)
    experience: Mapped[list] = mapped_column(JSONB, default=list)
    skills: Mapped[list] = mapped_column(JSONB, default=list)
    desired_position: Mapped[str | None] = mapped_column(String(200))
    expected_salary: Mapped[str | None] = mapped_column(String(100))
    years_experience: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text)
    match_score: Mapped[int | None] = mapped_column(SmallInteger)  # 0-100 fit vs. positioning
    match_notes: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(20), default="attachment")  # attachment | body


class CustomerProfile(Base, TimestampMixin):
    """Aggregated profile for an external correspondent (customer / supplier),
    keyed by their email address. Powers history-aware AI replies."""
    __tablename__ = "customer_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    company: Mapped[str | None] = mapped_column(String(200))
    email_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/lead/customer/complaint
    importance: Mapped[int] = mapped_column(SmallInteger, default=1)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    summary: Mapped[str | None] = mapped_column(Text)  # optional AI-written profile blurb
    notes: Mapped[str | None] = mapped_column(Text)
