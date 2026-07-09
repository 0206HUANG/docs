"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("domain", sa.String(100), nullable=False, unique=True),
        sa.Column("plan", sa.String(20), server_default="free"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("settings", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_departments_tenant_id", "departments", ["tenant_id"])

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("hashed_pw", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_id_email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("permissions", postgresql.JSONB, server_default="{}"),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id"), primary_key=True, nullable=True),
    )

    op.create_table(
        "email_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("email_address", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(100)),
        sa.Column("provider", sa.String(50), server_default="generic"),
        sa.Column("imap_host", sa.String(200), nullable=False),
        sa.Column("imap_port", sa.Integer, server_default="993"),
        sa.Column("imap_ssl", sa.Boolean, server_default="true"),
        sa.Column("smtp_host", sa.String(200), nullable=False),
        sa.Column("smtp_port", sa.Integer, server_default="465"),
        sa.Column("smtp_ssl", sa.Boolean, server_default="true"),
        sa.Column("username", sa.String(200), nullable=False),
        sa.Column("password_enc", sa.Text, nullable=False),
        sa.Column("positioning", sa.String(50), server_default="general"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("sync_status", sa.String(20), server_default="idle"),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_email_accounts_tenant_id", "email_accounts", ["tenant_id"])

    op.create_table(
        "email_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_accounts.id"), nullable=False),
        sa.Column("subject", sa.String(500)),
        sa.Column("participants", postgresql.JSONB, server_default="[]"),
        sa.Column("last_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), server_default="open"),
    )
    op.create_index("ix_email_threads_tenant_id", "email_threads", ["tenant_id"])

    op.create_table(
        "emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_accounts.id"), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_threads.id")),
        sa.Column("message_id", sa.String(500), nullable=False, unique=True),
        sa.Column("in_reply_to", sa.String(500)),
        sa.Column("references", sa.Text),
        sa.Column("direction", sa.String(10), server_default="inbound"),
        sa.Column("from_addr", sa.String(500), nullable=False),
        sa.Column("from_name", sa.String(200)),
        sa.Column("to_addrs", postgresql.JSONB, server_default="[]"),
        sa.Column("cc_addrs", postgresql.JSONB, server_default="[]"),
        sa.Column("subject", sa.String(500)),
        sa.Column("body_text", sa.Text),
        sa.Column("body_html", sa.Text),
        sa.Column("language", sa.String(10)),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_emails_tenant_id", "emails", ["tenant_id"])
    op.create_index("ix_emails_tenant_received", "emails", ["tenant_id", "received_at"])

    op.create_table(
        "email_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("emails.id"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100)),
        sa.Column("size_bytes", sa.Integer, server_default="0"),
        sa.Column("storage_path", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "email_classifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("emails.id"), unique=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_type", sa.String(50), nullable=False),
        sa.Column("language", sa.String(10)),
        sa.Column("urgency", sa.SmallInteger, server_default="1"),
        sa.Column("has_sensitive", sa.Boolean, server_default="false"),
        sa.Column("sensitive_words", postgresql.JSONB, server_default="[]"),
        sa.Column("confidence", sa.Float),
        sa.Column("llm_model", sa.String(100)),
        sa.Column("prompt_tokens", sa.Integer, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, server_default="0"),
        sa.Column("classified_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_email_classifications_tenant_id", "email_classifications", ["tenant_id"])

    op.create_table(
        "email_replies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("emails.id"), unique=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("draft_content", sa.Text),
        sa.Column("final_content", sa.Text),
        sa.Column("status", sa.String(20), server_default="pending_review"),
        sa.Column("send_strategy", sa.String(20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("llm_model", sa.String(100)),
        sa.Column("rag_chunk_ids", postgresql.JSONB, server_default="[]"),
        sa.Column("attached_asset_ids", postgresql.JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_email_replies_tenant_id", "email_replies", ["tenant_id"])

    op.create_table(
        "kb_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), server_default="general"),
        sa.Column("positioning", postgresql.JSONB, server_default="[]"),
        sa.Column("email_types", postgresql.JSONB, server_default="[]"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kb_groups_tenant_id", "kb_groups", ["tenant_id"])

    op.create_table(
        "kb_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_groups.id"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("source_type", sa.String(20), server_default="manual"),
        sa.Column("storage_path", sa.Text),
        sa.Column("status", sa.String(20), server_default="processing"),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_kb_documents_tenant_id", "kb_documents", ["tenant_id"])

    op.create_table(
        "kb_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_documents.id"), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kb_groups.id"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, server_default="0"),
        sa.Column("embedding", sa.Text),  # stored as text, cast to vector at query time
        sa.Column("token_count", sa.Integer, server_default="0"),
    )
    op.create_index("ix_kb_chunks_tenant_id", "kb_chunks", ["tenant_id"])
    # Create ivfflat index after data is populated; skip here for fresh schema
    op.execute(
        "ALTER TABLE kb_chunks ALTER COLUMN embedding TYPE vector(1536) "
        "USING embedding::vector(1536)"
    )

    op.create_table(
        "asset_library",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100)),
        sa.Column("size_bytes", sa.Integer, server_default="0"),
        sa.Column("storage_path", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("tags", postgresql.JSONB, server_default="[]"),
        sa.Column("is_whitelist", sa.Boolean, server_default="false"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_asset_library_tenant_id", "asset_library", ["tenant_id"])

    op.create_table(
        "sensitive_words",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id")),
        sa.Column("word", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), server_default="custom"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "email_type_strategies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_type", sa.String(50), nullable=False),
        sa.Column("positioning", sa.String(50)),
        sa.Column("send_strategy", sa.String(20), nullable=False),
        sa.Column("kb_group_ids", postgresql.JSONB, server_default="[]"),
        sa.Column("tone", sa.String(20), server_default="business"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_email_type_strategies_tenant_id", "email_type_strategies", ["tenant_id"])

    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("emails.id"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_accounts.id"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("priority", sa.SmallInteger, server_default="1"),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_tickets_tenant_id", "tickets", ["tenant_id"])

    op.create_table(
        "ticket_replies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("reply_sent", sa.Boolean, server_default="false"),
        sa.Column("sent_email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("emails.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("ref_type", sa.String(30)),
        sa.Column("ref_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_tenant_id", "notifications", ["tenant_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("emails.id")),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("actor_type", sa.String(20), server_default="system"),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("detail", postgresql.JSONB, server_default="{}"),
        sa.Column("status", sa.String(20), server_default="success"),
        sa.Column("error_msg", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_email_id", "audit_logs", ["email_id"])
    op.create_index("ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"])

    op.create_table(
        "summary_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_type", sa.String(10), nullable=False),
        sa.Column("period_start", sa.String(10), nullable=False),
        sa.Column("period_end", sa.String(10), nullable=False),
        sa.Column("stats", postgresql.JSONB, server_default="{}"),
        sa.Column("pending_tickets", postgresql.JSONB, server_default="[]"),
        sa.Column("sent_to", postgresql.JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_summary_reports_tenant_id", "summary_reports", ["tenant_id"])


def downgrade() -> None:
    for table in [
        "summary_reports", "audit_logs", "notifications", "ticket_replies",
        "tickets", "email_type_strategies", "sensitive_words", "asset_library",
        "kb_chunks", "kb_documents", "kb_groups", "email_replies",
        "email_classifications", "email_attachments", "emails", "email_threads",
        "email_accounts", "user_roles", "roles", "users", "departments", "tenants",
    ]:
        op.drop_table(table)
    op.execute("DROP EXTENSION IF EXISTS vector")
