import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DB
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models import EmailAccount, ScheduledEmail

router = APIRouter()


def _serialize(s: ScheduledEmail) -> dict:
    return {
        "id": str(s.id),
        "account_id": str(s.account_id),
        "to_addrs": s.to_addrs,
        "subject": s.subject,
        "scheduled_at": s.scheduled_at.isoformat() if s.scheduled_at else None,
        "status": s.status,
        "sent_at": s.sent_at.isoformat() if s.sent_at else None,
        "error_msg": s.error_msg,
        "track_opens": s.track_opens,
        "open_count": s.open_count,
        "first_opened_at": s.first_opened_at.isoformat() if s.first_opened_at else None,
        "last_opened_at": s.last_opened_at.isoformat() if s.last_opened_at else None,
    }


@router.post("")
async def schedule_email(body: dict, current_user: CurrentUser, db: DB):
    """Queue an email for future sending. Provide scheduled_at (ISO) or delay_minutes."""
    account = (await db.execute(
        select(EmailAccount).where(
            EmailAccount.id == uuid.UUID(body["account_id"]),
            EmailAccount.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not account:
        raise NotFoundError("EmailAccount")

    to_addrs = body.get("to_addrs") or []
    if not to_addrs or not body.get("subject") or not body.get("body_text"):
        raise ValidationError("to_addrs, subject and body_text are required")

    if body.get("scheduled_at"):
        when = datetime.fromisoformat(body["scheduled_at"])
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
    else:
        when = datetime.now(timezone.utc) + timedelta(minutes=int(body.get("delay_minutes", 0)))

    s = ScheduledEmail(
        tenant_id=current_user.tenant_id,
        account_id=account.id,
        to_addrs=to_addrs,
        cc_addrs=body.get("cc_addrs") or [],
        subject=body["subject"],
        body_text=body["body_text"],
        scheduled_at=when,
        track_opens=bool(body.get("track_opens", False)),
        created_by=current_user.id,
    )
    db.add(s)
    await db.commit()
    return {"id": str(s.id), "scheduled_at": when.isoformat(), "tracking_id": str(s.tracking_id)}


@router.get("")
async def list_scheduled(current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(ScheduledEmail)
        .where(ScheduledEmail.tenant_id == current_user.tenant_id)
        .order_by(ScheduledEmail.scheduled_at.desc())
        .limit(100)
    )
    return [_serialize(s) for s in result.scalars().all()]


@router.post("/{scheduled_id}/cancel")
async def cancel_scheduled(scheduled_id: str, current_user: CurrentUser, db: DB):
    """撤回：cancel a queued email before it is sent."""
    s = (await db.execute(
        select(ScheduledEmail).where(
            ScheduledEmail.id == uuid.UUID(scheduled_id),
            ScheduledEmail.tenant_id == current_user.tenant_id,
        )
    )).scalar_one_or_none()
    if not s:
        raise NotFoundError("ScheduledEmail")
    if s.status != "pending":
        raise ValidationError(f"Cannot cancel: status is '{s.status}' (already sent?)")
    s.status = "cancelled"
    await db.commit()
    return {"ok": True, "status": s.status}
