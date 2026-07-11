from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DB
from app.core.exceptions import PermissionError
from app.core.permissions import RoleName, role_level
from app.db.models import AuditLog, Email, EmailClassification, SummaryReport, Ticket

router = APIRouter()


def _require_manager(current_user):
    if max((role_level(ur.role.name) for ur in current_user.user_roles), default=0) < role_level(RoleName.DEPT_MANAGER):
        raise PermissionError()


@router.get("/stats")
async def stats(current_user: CurrentUser, db: DB):
    _require_manager(current_user)
    from datetime import datetime, timezone, timedelta
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today - timedelta(days=today.weekday())
    tid = current_user.tenant_id

    emails_today = (await db.execute(
        select(func.count(Email.id))
        .where(Email.tenant_id == tid, Email.received_at >= today)
    )).scalar_one()

    emails_week = (await db.execute(
        select(func.count(Email.id))
        .where(Email.tenant_id == tid, Email.received_at >= week_start)
    )).scalar_one()

    open_tickets = (await db.execute(
        select(func.count(Ticket.id))
        .where(Ticket.tenant_id == tid, Ticket.status.in_(["open", "claimed"]))
    )).scalar_one()

    auto_sent = (await db.execute(
        select(func.count(EmailClassification.id))
        .join(Email, EmailClassification.email_id == Email.id)
        .where(Email.tenant_id == tid, Email.received_at >= week_start,
               EmailClassification.has_sensitive == False)
    )).scalar_one()

    high_risk = (await db.execute(
        select(func.count(EmailClassification.id))
        .join(Email, EmailClassification.email_id == Email.id)
        .where(Email.tenant_id == tid, Email.received_at >= week_start,
               EmailClassification.has_sensitive == True)
    )).scalar_one()

    return {
        "emails_today": emails_today,
        "emails_week": emails_week,
        "open_tickets": open_tickets,
        "auto_sent_week": auto_sent,
        "high_risk_week": high_risk,
    }


@router.get("/summaries")
async def list_summaries(current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(SummaryReport)
        .where(SummaryReport.tenant_id == current_user.tenant_id)
        .order_by(SummaryReport.created_at.desc())
        .limit(30)
    )
    reports = result.scalars().all()
    return [
        {
            "id": str(r.id), "period_type": r.period_type,
            "period_start": r.period_start, "period_end": r.period_end,
            "stats": r.stats,
        }
        for r in reports
    ]


@router.get("/audit")
async def audit_logs(
    current_user: CurrentUser,
    db: DB,
    email_id: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    _require_manager(current_user)
    import uuid
    q = select(AuditLog).where(AuditLog.tenant_id == current_user.tenant_id)
    if email_id:
        q = q.where(AuditLog.email_id == uuid.UUID(email_id))
    q = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)
    logs = result.scalars().all()
    return [
        {
            "id": str(l.id), "email_id": str(l.email_id) if l.email_id else None,
            "stage": l.stage, "status": l.status,
            "detail": l.detail, "error_msg": l.error_msg,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]
