import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DB
from app.core.exceptions import NotFoundError
from app.db.models import Ticket, TicketReply

router = APIRouter()


@router.get("")
async def list_tickets(current_user: CurrentUser, db: DB, status: str | None = None):
    q = select(Ticket).where(Ticket.tenant_id == current_user.tenant_id)
    if status:
        q = q.where(Ticket.status == status)
    result = await db.execute(q.order_by(Ticket.created_at.desc()).limit(200))
    tickets = result.scalars().all()
    return [_ticket_dict(t) for t in tickets]


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: str, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(Ticket)
        .where(Ticket.id == uuid.UUID(ticket_id), Ticket.tenant_id == current_user.tenant_id)
        .options(selectinload(Ticket.replies))
    )
    t = result.scalar_one_or_none()
    if not t:
        raise NotFoundError("Ticket")
    d = _ticket_dict(t)
    d["replies"] = [
        {"id": str(r.id), "content": r.content, "created_at": r.created_at.isoformat()}
        for r in t.replies
    ]
    return d


@router.post("/{ticket_id}/claim")
async def claim_ticket(ticket_id: str, current_user: CurrentUser, db: DB):
    t = await _get_ticket(ticket_id, current_user, db)
    t.assigned_to = current_user.id
    t.status = "claimed"
    t.claimed_at = datetime.now(timezone.utc)
    await db.commit()
    return _ticket_dict(t)


@router.post("/{ticket_id}/reply")
async def add_reply(ticket_id: str, body: dict, current_user: CurrentUser, db: DB):
    t = await _get_ticket(ticket_id, current_user, db)
    tr = TicketReply(
        ticket_id=t.id,
        tenant_id=current_user.tenant_id,
        author_id=current_user.id,
        content=body.get("content", ""),
    )
    db.add(tr)
    await db.commit()
    return {"id": str(tr.id)}


@router.post("/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, current_user: CurrentUser, db: DB):
    t = await _get_ticket(ticket_id, current_user, db)
    t.status = "resolved"
    t.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return _ticket_dict(t)


async def _get_ticket(ticket_id: str, current_user, db) -> Ticket:
    result = await db.execute(
        select(Ticket).where(
            Ticket.id == uuid.UUID(ticket_id),
            Ticket.tenant_id == current_user.tenant_id,
        )
    )
    t = result.scalar_one_or_none()
    if not t:
        raise NotFoundError("Ticket")
    return t


def _ticket_dict(t: Ticket) -> dict:
    return {
        "id": str(t.id),
        "title": t.title,
        "reason": t.reason,
        "status": t.status,
        "priority": t.priority,
        "assigned_to": str(t.assigned_to) if t.assigned_to else None,
        "created_at": t.created_at.isoformat(),
    }
