import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import AuditLog, Email, EmailClassification, EmailReply, EmailThread
from app.repos.base import TenantBaseRepo


class EmailRepo(TenantBaseRepo[Email]):
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(Email, db, tenant_id)

    async def get_by_message_id(self, message_id: str) -> Email | None:
        result = await self.db.execute(
            select(Email).where(Email.message_id == message_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_thread(
        self,
        account_id: uuid.UUID,
        subject: str | None,
        in_reply_to: str | None,
        references: str | None,
    ) -> EmailThread:
        if in_reply_to or references:
            ref_ids: set[str] = set()
            if in_reply_to:
                ref_ids.add(in_reply_to.strip())
            if references:
                ref_ids.update(r.strip() for r in references.split() if r.strip())
            if ref_ids:
                result = await self.db.execute(
                    select(EmailThread)
                    .join(Email, Email.thread_id == EmailThread.id)
                    .where(
                        and_(
                            EmailThread.tenant_id == self.tenant_id,
                            EmailThread.account_id == account_id,
                            Email.message_id.in_(ref_ids),
                        )
                    )
                    .limit(1)
                )
                thread = result.scalar_one_or_none()
                if thread:
                    return thread

        thread = EmailThread(
            tenant_id=self.tenant_id,
            account_id=account_id,
            subject=subject,
        )
        self.db.add(thread)
        await self.db.flush()
        return thread

    async def list_inbox(
        self,
        account_ids: list[uuid.UUID] | None = None,
        email_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Email], int]:
        q = (
            self._base_query()
            .where(Email.direction == "inbound")
            .options(
                selectinload(Email.classification),
                selectinload(Email.reply),
            )
        )
        if account_ids:
            q = q.where(Email.account_id.in_(account_ids))
        if email_type:
            q = q.join(
                EmailClassification,
                EmailClassification.email_id == Email.id
            ).where(EmailClassification.email_type == email_type)
        if date_from:
            q = q.where(Email.received_at >= date_from)
        if date_to:
            q = q.where(Email.received_at <= date_to)

        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        q = q.order_by(Email.received_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all()), total


class AuditLogRepo:
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def log(
        self,
        email_id: uuid.UUID | None,
        stage: str,
        status: str = "success",
        detail: dict | None = None,
        error_msg: str | None = None,
        actor_type: str = "system",
        actor_id: uuid.UUID | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            tenant_id=self.tenant_id,
            email_id=email_id,
            stage=stage,
            status=status,
            detail=detail or {},
            error_msg=error_msg,
            actor_type=actor_type,
            actor_id=actor_id,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(entry)
        await self.db.flush()
        return entry
