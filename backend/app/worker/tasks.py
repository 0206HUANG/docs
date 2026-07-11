import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import redis.asyncio as redis
from arq import ArqRedis
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.base import AsyncSessionLocal
from app.db.models import Email, EmailAccount, EmailAttachment, EmailReply, Tenant
from app.services.mail import get_mail_provider
from app.services.mail.base import OutboundEmail

logger = logging.getLogger(__name__)

_arq_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    global _arq_pool
    if not _arq_pool:
        from arq.connections import RedisSettings, create_pool
        _arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    return _arq_pool


async def enqueue_send_reply(reply_id: str) -> None:
    pool = await get_arq_pool()
    await pool.enqueue_job("send_reply", reply_id)


async def enqueue_process_email(email_id: str) -> None:
    pool = await get_arq_pool()
    await pool.enqueue_job("process_email", email_id)


# ── ARQ Task Handlers ────────────────────────────────────────────────────────

async def poll_inbox(ctx: dict, account_id: str) -> None:
    """Poll one email account for new messages."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(EmailAccount)
            .where(EmailAccount.id == uuid.UUID(account_id), EmailAccount.is_active == True)
            .options(selectinload(EmailAccount.tenant))
        )
        account = result.scalar_one_or_none()
        if not account:
            return

        try:
            provider = get_mail_provider(account)
            since = account.last_synced_at or (datetime.now(timezone.utc) - timedelta(days=1))
            raw_emails = await provider.fetch_new(since=since)

            from app.repos.email_repo import EmailRepo
            email_repo = EmailRepo(db, account.tenant_id)

            new_count = 0
            for raw in raw_emails:
                # Dedup by message_id
                existing = await email_repo.get_by_message_id(raw.message_id)
                if existing:
                    continue

                thread = await email_repo.get_or_create_thread(
                    account_id=account.id,
                    subject=raw.subject,
                    in_reply_to=raw.in_reply_to,
                    references=raw.references,
                )
                email = Email(
                    tenant_id=account.tenant_id,
                    account_id=account.id,
                    thread_id=thread.id,
                    message_id=raw.message_id,
                    in_reply_to=raw.in_reply_to,
                    references=raw.references,
                    direction="inbound",
                    from_addr=raw.from_addr,
                    from_name=raw.from_name,
                    to_addrs=raw.to_addrs,
                    cc_addrs=raw.cc_addrs,
                    subject=raw.subject,
                    body_text=raw.body_text,
                    body_html=raw.body_html,
                    received_at=raw.received_at,
                )
                db.add(email)
                await db.flush()
                new_count += 1

                # Persist attachments (needed for resume parsing / asset use)
                for att in raw.attachments:
                    data = att.get("data") or b""
                    storage_dir = os.path.join(
                        settings.STORAGE_PATH, str(account.tenant_id), "attachments"
                    )
                    os.makedirs(storage_dir, exist_ok=True)
                    safe_name = (att.get("filename") or "attachment").replace("/", "_").replace("\\", "_")
                    fpath = os.path.join(storage_dir, f"{email.id}_{safe_name}")
                    try:
                        with open(fpath, "wb") as fh:
                            fh.write(data)
                    except Exception as e:
                        logger.warning("Failed to store attachment %s: %s", safe_name, e)
                        continue
                    db.add(EmailAttachment(
                        email_id=email.id,
                        tenant_id=account.tenant_id,
                        filename=safe_name,
                        content_type=att.get("content_type"),
                        size_bytes=len(data),
                        storage_path=fpath,
                    ))
                await db.flush()

                # If this sender is a target of an active campaign, stop its SOP
                from app.services.campaign import mark_replied
                await mark_replied(db, account.tenant_id, raw.from_addr)

                # Enqueue pipeline processing
                await enqueue_process_email(str(email.id))

            # Update sync timestamp
            account.last_synced_at = datetime.now(timezone.utc)
            account.sync_status = "idle"
            account.error_message = None
            await db.commit()
            logger.info("Polled account %s: %d new emails", account.email_address, new_count)

        except Exception as e:
            logger.error("Poll failed for account %s: %s", account_id, e)
            account.sync_status = "error"
            account.error_message = str(e)[:500]
            await db.commit()
            raise  # ARQ will retry


async def process_email(ctx: dict, email_id: str) -> None:
    """Run the full classification → RAG → reply pipeline for one email."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Email)
            .where(Email.id == uuid.UUID(email_id))
            .options(selectinload(Email.account))
        )
        email = result.scalar_one_or_none()
        if not email:
            logger.warning("process_email: email %s not found", email_id)
            return

        account = email.account
        tenant_result = await db.execute(select(Tenant).where(Tenant.id == email.tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        if not tenant or not tenant.is_active:
            return

        from app.services.pipeline.orchestrator import process_email as run_pipeline
        await run_pipeline(db=db, email=email, account=account, tenant_settings=tenant.settings)


async def send_reply(ctx: dict, reply_id: str) -> None:
    """Send a reply email via SMTP."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(EmailReply)
            .where(EmailReply.id == uuid.UUID(reply_id))
            .options(selectinload(EmailReply.email).selectinload(Email.account))
        )
        reply = result.scalar_one_or_none()
        if not reply or reply.status == "sent":
            return

        email = reply.email
        account = email.account
        content = reply.final_content or reply.draft_content or ""

        outbound = OutboundEmail(
            from_addr=account.email_address,
            from_name=account.display_name,
            to_addrs=[email.from_addr],
            cc_addrs=[],
            subject=f"Re: {email.subject or ''}",
            body_text=content,
            in_reply_to=email.message_id,
            references=email.message_id,
        )
        try:
            provider = get_mail_provider(account)
            await provider.send(outbound)
            reply.status = "sent"
            reply.sent_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info("Reply sent for email %s", email.id)
        except Exception as e:
            logger.error("SMTP send failed reply=%s: %s", reply_id, e)
            raise


async def generate_summary(ctx: dict, tenant_id: str, period_type: str) -> None:
    """Generate and email a summary report."""
    from datetime import date
    async with AsyncSessionLocal() as db:
        from app.services.summary import build_and_send_summary
        await build_and_send_summary(db, uuid.UUID(tenant_id), period_type)


async def ingest_document(ctx: dict, document_id: str, content: bytes) -> None:
    """Background KB document ingestion: extract, chunk, embed, store."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select as sa_select
        from app.db.models import KBDocument, Tenant
        from app.services.kb.ingestion import ingest_document as run_ingest
        from app.services.llm import get_embed_provider

        result = await db.execute(sa_select(KBDocument).where(KBDocument.id == uuid.UUID(document_id)))
        doc = result.scalar_one_or_none()
        if not doc:
            return

        tenant_result = await db.execute(sa_select(Tenant).where(Tenant.id == doc.tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            return

        llm_config = tenant.settings.get("llm_config", {})
        embed_provider = get_embed_provider(llm_config)
        chunk_count = await run_ingest(db=db, document=doc, content=content, embed_provider=embed_provider)
        logger.info("Ingested document %s: %d chunks", document_id, chunk_count)


async def poll_all_accounts(ctx: dict) -> None:
    """Cron: poll every active email account."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(EmailAccount).where(EmailAccount.is_active == True)
        )
        accounts = result.scalars().all()

    pool = await get_arq_pool()
    for account in accounts:
        await pool.enqueue_job("poll_inbox", str(account.id))
    logger.info("Queued polling for %d accounts", len(accounts))


async def escalate_tickets(ctx: dict) -> None:
    """Cron: escalate overdue open/claimed tickets and notify admins."""
    async with AsyncSessionLocal() as db:
        from app.services.escalation import escalate_overdue
        await escalate_overdue(db)


async def run_campaigns(ctx: dict) -> None:
    """Cron: send due SOP steps for running outbound campaigns."""
    async with AsyncSessionLocal() as db:
        from app.services.campaign import run_due_recipients
        await run_due_recipients(db)


async def send_scheduled(ctx: dict) -> None:
    """Cron (every minute): dispatch due scheduled emails."""
    async with AsyncSessionLocal() as db:
        from app.services.outbox import send_due_scheduled
        await send_due_scheduled(db)
