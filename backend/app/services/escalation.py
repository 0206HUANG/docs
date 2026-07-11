"""
Overdue-ticket escalation. A cron job scans open/claimed tickets and, when one
has sat past the SLA for its priority, bumps its priority, raises its
escalation level, and notifies the tenant's admins — so human-routed requests
never sit unattended (PDF: "避免客户/供应商诉求无人跟进流失").
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification, Role, Ticket, User, UserRole

logger = logging.getLogger(__name__)

# priority → hours a ticket may sit before it first escalates
THRESHOLDS_H = {3: 2, 2: 8, 1: 24}
# minimum hours between repeat escalations of the same ticket
ESCALATION_INTERVAL_H = 4


async def _get_admins(db: AsyncSession, tenant_id) -> list[User]:
    result = await db.execute(
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            User.tenant_id == tenant_id,
            User.is_active == True,
            Role.name.in_(["TENANT_ADMIN", "SUPER_ADMIN"]),
        )
    )
    return list(result.scalars().unique().all())


async def escalate_overdue(db: AsyncSession, now: datetime | None = None) -> int:
    """Escalate overdue open/claimed tickets. Returns how many were escalated."""
    now = now or datetime.now(timezone.utc)
    result = await db.execute(select(Ticket).where(Ticket.status.in_(["open", "claimed"])))
    tickets = result.scalars().all()

    escalated = 0
    admins_by_tenant: dict = {}
    for t in tickets:
        if not t.created_at:
            continue
        threshold = THRESHOLDS_H.get(t.priority, 24)
        age_h = (now - t.created_at).total_seconds() / 3600
        if age_h < threshold:
            continue
        if t.last_escalated_at:
            since = (now - t.last_escalated_at).total_seconds() / 3600
            if since < ESCALATION_INTERVAL_H:
                continue

        t.escalation_level = (t.escalation_level or 0) + 1
        t.last_escalated_at = now
        if t.priority < 3:
            t.priority += 1

        if t.tenant_id not in admins_by_tenant:
            admins_by_tenant[t.tenant_id] = await _get_admins(db, t.tenant_id)
        for u in admins_by_tenant[t.tenant_id]:
            db.add(Notification(
                tenant_id=t.tenant_id,
                user_id=u.id,
                type="ticket_escalation",
                title=f"[超时升级 L{t.escalation_level}] {t.title}",
                body=f"工单已超时约 {int(age_h)} 小时未处理(状态={t.status})，请尽快跟进。",
                ref_type="ticket",
                ref_id=t.id,
            ))
        escalated += 1

    await db.commit()
    if escalated:
        logger.info("Escalated %d overdue tickets", escalated)
    return escalated
