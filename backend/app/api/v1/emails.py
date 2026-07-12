import uuid
from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DB
from app.core.exceptions import NotFoundError
from app.db.models import AuditLog, Email, EmailAccount, EmailClassification, EmailReply
from app.repos.email_repo import EmailRepo

router = APIRouter()


@router.get("")
async def list_emails(
    current_user: CurrentUser,
    db: DB,
    account_id: str | None = Query(None),
    email_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    repo = EmailRepo(db, current_user.tenant_id)
    account_ids = [uuid.UUID(account_id)] if account_id else None
    emails, total = await repo.list_inbox(
        account_ids=account_ids,
        email_type=email_type,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "items": [_email_summary(e) for e in emails],
    }


@router.post("/sync")
async def sync_emails(current_user: CurrentUser, db: DB):
    """Trigger an immediate inbox poll for all active accounts of this tenant."""
    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.tenant_id == current_user.tenant_id,
            EmailAccount.is_active == True,
        )
    )
    accounts = result.scalars().all()
    from app.worker.tasks import get_arq_pool
    pool = await get_arq_pool()
    for a in accounts:
        await pool.enqueue_job("poll_inbox", str(a.id))
    return {"queued": len(accounts)}


@router.get("/{email_id}")
async def get_email(email_id: str, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(Email)
        .where(Email.id == uuid.UUID(email_id), Email.tenant_id == current_user.tenant_id)
        .options(
            selectinload(Email.classification),
            selectinload(Email.reply),
            selectinload(Email.attachments),
        )
    )
    email = result.scalar_one_or_none()
    if not email:
        raise NotFoundError("Email")
    return _email_detail(email)


@router.get("/{email_id}/audit")
async def get_audit(email_id: str, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.email_id == uuid.UUID(email_id),
            AuditLog.tenant_id == current_user.tenant_id,
        )
        .order_by(AuditLog.created_at)
    )
    logs = result.scalars().all()
    return [
        {
            "stage": l.stage, "status": l.status,
            "detail": l.detail, "error_msg": l.error_msg,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]


def _email_summary(e: Email) -> dict:
    cls = e.classification
    return {
        "id": str(e.id),
        "from_addr": e.from_addr,
        "from_name": e.from_name,
        "subject": e.subject,
        "received_at": e.received_at.isoformat() if e.received_at else None,
        "email_type": cls.email_type if cls else None,
        "urgency": cls.urgency if cls else None,
        "has_sensitive": cls.has_sensitive if cls else False,
        "reply_status": e.reply.status if e.reply else None,
    }


def _email_detail(e: Email) -> dict:
    base = _email_summary(e)
    cls = e.classification
    base.update({
        "body_text": e.body_text,
        "language": cls.language if cls else None,
        "reply": {
            "id": str(e.reply.id),
            "draft_content": e.reply.draft_content,
            "final_content": e.reply.final_content,
            "status": e.reply.status,
            "send_strategy": e.reply.send_strategy,
        } if e.reply else None,
        "attachments": [
            {"id": str(a.id), "filename": a.filename, "content_type": a.content_type}
            for a in e.attachments
        ],
    })
    return base
