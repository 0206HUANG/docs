import uuid

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DB
from app.core.exceptions import NotFoundError
from app.db.models import CustomerProfile, Email

router = APIRouter()


def _serialize(c: CustomerProfile) -> dict:
    return {
        "id": str(c.id),
        "email": c.email,
        "name": c.name,
        "company": c.company,
        "email_count": c.email_count,
        "first_seen": c.first_seen.isoformat() if c.first_seen else None,
        "last_seen": c.last_seen.isoformat() if c.last_seen else None,
        "status": c.status,
        "importance": c.importance,
        "tags": c.tags,
        "summary": c.summary,
        "notes": c.notes,
    }


@router.get("")
async def list_customers(
    current_user: CurrentUser,
    db: DB,
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    result = await db.execute(
        select(CustomerProfile)
        .where(CustomerProfile.tenant_id == current_user.tenant_id)
        .order_by(CustomerProfile.last_seen.desc().nullslast())
        .offset(offset)
        .limit(limit)
    )
    return [_serialize(c) for c in result.scalars().all()]


@router.get("/{customer_id}")
async def get_customer(customer_id: str, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(CustomerProfile).where(
            CustomerProfile.id == uuid.UUID(customer_id),
            CustomerProfile.tenant_id == current_user.tenant_id,
        )
    )
    c = result.scalar_one_or_none()
    if not c:
        raise NotFoundError("Customer")

    emails_result = await db.execute(
        select(Email)
        .where(
            Email.tenant_id == current_user.tenant_id,
            func.lower(Email.from_addr) == c.email,
        )
        .order_by(Email.received_at.desc().nullslast())
        .limit(20)
    )
    recent = [
        {
            "id": str(e.id),
            "subject": e.subject,
            "received_at": e.received_at.isoformat() if e.received_at else None,
            "snippet": (e.body_text or "")[:120],
        }
        for e in emails_result.scalars().all()
    ]
    return {**_serialize(c), "recent_emails": recent}
