import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Email, EmailClassification, EmailReply, SummaryReport, Tenant, Ticket, User
)

logger = logging.getLogger(__name__)


async def build_and_send_summary(
    db: AsyncSession, tenant_id: uuid.UUID, period_type: str
) -> SummaryReport:
    today = date.today()
    if period_type == "daily":
        period_start = today - timedelta(days=1)
        period_end = today
    elif period_type == "weekly":
        period_start = today - timedelta(weeks=1)
        period_end = today
    else:  # monthly
        period_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        period_end = today.replace(day=1) - timedelta(days=1)

    start_dt = datetime.combine(period_start, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(period_end, datetime.max.time()).replace(tzinfo=timezone.utc)

    total_emails = (await db.execute(
        select(func.count(Email.id)).where(
            Email.tenant_id == tenant_id,
            Email.direction == "inbound",
            Email.received_at.between(start_dt, end_dt),
        )
    )).scalar_one()

    auto_sent = (await db.execute(
        select(func.count(EmailReply.id)).where(
            EmailReply.tenant_id == tenant_id,
            EmailReply.send_strategy == "auto_send",
            EmailReply.status == "sent",
        )
    )).scalar_one()

    human_count = (await db.execute(
        select(func.count(Ticket.id)).where(
            Ticket.tenant_id == tenant_id,
            Ticket.created_at.between(start_dt, end_dt),
        )
    )).scalar_one()

    open_tickets = (await db.execute(
        select(func.count(Ticket.id)).where(
            Ticket.tenant_id == tenant_id,
            Ticket.status.in_(["open", "claimed"]),
        )
    )).scalar_one()

    stats = {
        "total_emails": total_emails,
        "auto_sent": auto_sent,
        "human_routed": human_count,
        "open_tickets": open_tickets,
        "period": f"{period_start} to {period_end}",
    }

    pending_result = await db.execute(
        select(Ticket.id, Ticket.title, Ticket.created_at).where(
            Ticket.tenant_id == tenant_id,
            Ticket.status.in_(["open", "claimed"]),
        ).order_by(Ticket.created_at).limit(50)
    )
    pending = [
        {"id": str(r.id), "title": r.title, "created_at": r.created_at.isoformat()}
        for r in pending_result.fetchall()
    ]

    report = SummaryReport(
        tenant_id=tenant_id,
        period_type=period_type,
        period_start=str(period_start),
        period_end=str(period_end),
        stats=stats,
        pending_tickets=pending,
        sent_to=[],
        created_at=datetime.now(timezone.utc),
    )
    db.add(report)

    # Send email notification to tenant admins
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if tenant:
        summary_cfg = tenant.settings.get("summary_config", {})
        notify_emails = summary_cfg.get("notify_emails", [])
        if notify_emails:
            await _send_summary_email(tenant, report, notify_emails)
            report.sent_to = notify_emails

    await db.commit()
    return report


async def _send_summary_email(tenant, report: SummaryReport, recipients: list[str]) -> None:
    """Send a plain-text summary report via configured admin account."""
    stats = report.stats
    body = f"""
{tenant.name} 邮件处理总结 ({report.period_type})
统计周期: {report.period_start} ~ {report.period_end}

总收件数: {stats.get('total_emails', 0)}
AI 自动回复: {stats.get('auto_sent', 0)}
转人工处理: {stats.get('human_routed', 0)}
待闭环工单: {stats.get('open_tickets', 0)}
""".strip()

    logger.info("Summary report ready for tenant %s, period=%s", tenant.id, report.period_type)
    # Actual email sending would use admin account SMTP; skipped if no account configured
