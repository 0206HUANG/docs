import uuid
from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DB
from app.db.models import Notification

router = APIRouter()


@router.get("")
async def list_notifications(current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.tenant_id == current_user.tenant_id,
        )
        .order_by(Notification.created_at.desc())
        .limit(100)
    )
    items = result.scalars().all()
    return [
        {
            "id": str(n.id), "type": n.type, "title": n.title,
            "body": n.body, "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        }
        for n in items
    ]


@router.post("/{notif_id}/read")
async def mark_read(notif_id: str, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(Notification).where(
            Notification.id == uuid.UUID(notif_id),
            Notification.user_id == current_user.id,
        )
    )
    n = result.scalar_one_or_none()
    if n:
        n.is_read = True
        await db.commit()
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(current_user: CurrentUser, db: DB):
    from sqlalchemy import update
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.tenant_id == current_user.tenant_id,
            Notification.is_read == False,
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}
