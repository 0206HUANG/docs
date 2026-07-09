import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EmailTypeStrategy, Notification, SensitiveWord, Ticket
from app.repos.base import TenantBaseRepo


class TicketRepo(TenantBaseRepo[Ticket]):
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(Ticket, db, tenant_id)

    async def get_open_for_user(self, user_id: uuid.UUID | None = None) -> list[Ticket]:
        q = self._base_query().where(Ticket.status.in_(["open", "claimed"]))
        if user_id:
            q = q.where(Ticket.assigned_to == user_id)
        result = await self.db.execute(q.order_by(Ticket.created_at.desc()))
        return list(result.scalars().all())


class NotificationRepo(TenantBaseRepo[Notification]):
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(Notification, db, tenant_id)

    async def get_for_user(self, user_id: uuid.UUID, unread_only: bool = False) -> list[Notification]:
        q = self._base_query().where(Notification.user_id == user_id)
        if unread_only:
            q = q.where(Notification.is_read == False)
        result = await self.db.execute(q.order_by(Notification.created_at.desc()).limit(100))
        return list(result.scalars().all())


class SensitiveWordRepo:
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def get_all_active(self) -> list[str]:
        result = await self.db.execute(
            select(SensitiveWord.word).where(
                SensitiveWord.is_active == True,
                or_(
                    SensitiveWord.tenant_id == self.tenant_id,
                    SensitiveWord.tenant_id == None,
                ),
            )
        )
        return [r[0] for r in result.fetchall()]


class StrategyRepo(TenantBaseRepo[EmailTypeStrategy]):
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(EmailTypeStrategy, db, tenant_id)

    async def get_strategy(
        self, email_type: str, positioning: str | None = None
    ) -> EmailTypeStrategy | None:
        q = self._base_query().where(
            EmailTypeStrategy.email_type == email_type,
            EmailTypeStrategy.is_active == True,
        )
        if positioning:
            q = q.where(
                or_(
                    EmailTypeStrategy.positioning == positioning,
                    EmailTypeStrategy.positioning == None,
                )
            ).order_by(EmailTypeStrategy.positioning.desc())
        result = await self.db.execute(q.limit(1))
        return result.scalar_one_or_none()
