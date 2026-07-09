from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DB
from app.core.exceptions import PermissionError
from app.core.permissions import RoleName, role_level
from app.core.security import encrypt_value
from app.db.models import EmailTypeStrategy, SensitiveWord

router = APIRouter()


def _require_admin(current_user):
    if max((role_level(ur.role.name) for ur in current_user.user_roles), default=0) < role_level(RoleName.TENANT_ADMIN):
        raise PermissionError()


@router.get("/strategies")
async def list_strategies(current_user: CurrentUser, db: DB):
    _require_admin(current_user)
    result = await db.execute(
        select(EmailTypeStrategy).where(EmailTypeStrategy.tenant_id == current_user.tenant_id)
    )
    items = result.scalars().all()
    return [
        {
            "id": str(s.id), "email_type": s.email_type,
            "positioning": s.positioning, "send_strategy": s.send_strategy,
            "tone": s.tone, "is_active": s.is_active,
        }
        for s in items
    ]


@router.put("/strategies/{email_type}")
async def update_strategy(email_type: str, body: dict, current_user: CurrentUser, db: DB):
    _require_admin(current_user)
    result = await db.execute(
        select(EmailTypeStrategy).where(
            EmailTypeStrategy.tenant_id == current_user.tenant_id,
            EmailTypeStrategy.email_type == email_type,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        strategy = EmailTypeStrategy(
            tenant_id=current_user.tenant_id,
            email_type=email_type,
            send_strategy=body.get("send_strategy", "draft_review"),
        )
        db.add(strategy)

    for field in ["send_strategy", "positioning", "tone", "is_active", "kb_group_ids"]:
        if field in body:
            setattr(strategy, field, body[field])
    await db.commit()
    return {"ok": True}


@router.get("/sensitive-words")
async def list_sensitive_words(current_user: CurrentUser, db: DB):
    _require_admin(current_user)
    result = await db.execute(
        select(SensitiveWord).where(
            (SensitiveWord.tenant_id == current_user.tenant_id) | (SensitiveWord.tenant_id == None)
        )
    )
    words = result.scalars().all()
    return [{"id": str(w.id), "word": w.word, "category": w.category, "is_active": w.is_active} for w in words]


@router.post("/sensitive-words")
async def add_sensitive_word(body: dict, current_user: CurrentUser, db: DB):
    _require_admin(current_user)
    w = SensitiveWord(
        tenant_id=current_user.tenant_id,
        word=body["word"],
        category=body.get("category", "custom"),
    )
    db.add(w)
    await db.commit()
    return {"id": str(w.id)}


@router.get("/llm")
async def get_llm_config(current_user: CurrentUser, db: DB):
    _require_admin(current_user)
    from sqlalchemy import select
    from app.db.models import Tenant
    result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        return {}
    cfg = tenant.settings.get("llm_config", {})
    # Mask the API key
    return {k: ("***" if "key" in k else v) for k, v in cfg.items()}


@router.put("/llm")
async def update_llm_config(body: dict, current_user: CurrentUser, db: DB):
    _require_admin(current_user)
    from app.db.models import Tenant
    result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise PermissionError()
    settings_copy = dict(tenant.settings or {})
    llm_cfg = dict(settings_copy.get("llm_config", {}))
    for k, v in body.items():
        if "key" in k and v and v != "***":
            llm_cfg[k] = encrypt_value(v)
        elif v and v != "***":
            llm_cfg[k] = v
    settings_copy["llm_config"] = llm_cfg
    tenant.settings = settings_copy
    await db.commit()
    return {"ok": True}
