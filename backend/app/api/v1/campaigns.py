import uuid

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DB
from app.core.exceptions import NotFoundError, PermissionError
from app.core.permissions import RoleName, role_level
from app.db.models import Campaign, CampaignRecipient

router = APIRouter()


def _require_manager(current_user):
    if max((role_level(ur.role.name) for ur in current_user.user_roles), default=0) < role_level(RoleName.DEPT_MANAGER):
        raise PermissionError()


async def _owned(db, campaign_id, tenant_id) -> Campaign:
    c = (await db.execute(
        select(Campaign).where(Campaign.id == uuid.UUID(campaign_id), Campaign.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not c:
        raise NotFoundError("Campaign")
    return c


@router.post("")
async def create_campaign(body: dict, current_user: CurrentUser, db: DB):
    _require_manager(current_user)
    c = Campaign(
        tenant_id=current_user.tenant_id,
        account_id=uuid.UUID(body["account_id"]),
        name=body["name"],
        subject_template=body["subject_template"],
        body_template=body["body_template"],
        sop_steps=body.get("sop_steps", 1),
        sop_interval_hours=body.get("sop_interval_hours", 72),
        tone=body.get("tone", "business"),
        language=body.get("language", "zh"),
        status="draft",
    )
    db.add(c)
    await db.commit()
    return {"id": str(c.id)}


@router.post("/{campaign_id}/recipients")
async def add_recipients(campaign_id: str, body: dict, current_user: CurrentUser, db: DB):
    _require_manager(current_user)
    c = await _owned(db, campaign_id, current_user.tenant_id)
    added = 0
    for item in body.get("recipients", []):
        email = (item.get("email") or "").strip().lower()
        if not email:
            continue
        db.add(CampaignRecipient(
            tenant_id=current_user.tenant_id, campaign_id=c.id,
            email=email, name=item.get("name"),
        ))
        added += 1
    await db.commit()
    return {"added": added}


@router.post("/{campaign_id}/start")
async def start_campaign(campaign_id: str, current_user: CurrentUser, db: DB):
    _require_manager(current_user)
    c = await _owned(db, campaign_id, current_user.tenant_id)
    c.status = "running"
    await db.commit()
    return {"ok": True, "status": c.status}


@router.post("/{campaign_id}/pause")
async def pause_campaign(campaign_id: str, current_user: CurrentUser, db: DB):
    _require_manager(current_user)
    c = await _owned(db, campaign_id, current_user.tenant_id)
    c.status = "paused"
    await db.commit()
    return {"ok": True, "status": c.status}


@router.get("")
async def list_campaigns(current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(Campaign).where(Campaign.tenant_id == current_user.tenant_id)
        .order_by(Campaign.created_at.desc())
    )
    out = []
    for c in result.scalars().all():
        counts = await db.execute(
            select(CampaignRecipient.status, func.count())
            .where(CampaignRecipient.campaign_id == c.id)
            .group_by(CampaignRecipient.status)
        )
        out.append({
            "id": str(c.id), "name": c.name, "status": c.status,
            "sop_steps": c.sop_steps, "sop_interval_hours": c.sop_interval_hours,
            "recipients": {s: n for s, n in counts.all()},
        })
    return out


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str, current_user: CurrentUser, db: DB):
    c = await _owned(db, campaign_id, current_user.tenant_id)
    recips = (await db.execute(
        select(CampaignRecipient).where(CampaignRecipient.campaign_id == c.id)
    )).scalars().all()
    return {
        "id": str(c.id), "name": c.name, "status": c.status,
        "subject_template": c.subject_template, "body_template": c.body_template,
        "sop_steps": c.sop_steps, "sop_interval_hours": c.sop_interval_hours,
        "recipients": [
            {
                "id": str(r.id), "email": r.email, "name": r.name,
                "current_step": r.current_step, "status": r.status,
                "last_sent_at": r.last_sent_at.isoformat() if r.last_sent_at else None,
                "next_send_at": r.next_send_at.isoformat() if r.next_send_at else None,
            }
            for r in recips
        ],
    }
