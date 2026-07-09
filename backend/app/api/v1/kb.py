import uuid
from fastapi import APIRouter, File, UploadFile, Form
from sqlalchemy import select

from app.api.deps import CurrentUser, DB
from app.core.exceptions import NotFoundError, PermissionError
from app.core.permissions import RoleName, role_level
from app.db.models import KBDocument, KBGroup

router = APIRouter()


def _require_manager(current_user):
    if max((role_level(ur.role.name) for ur in current_user.user_roles), default=0) < role_level(RoleName.DEPT_MANAGER):
        raise PermissionError()


@router.get("/groups")
async def list_groups(current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(KBGroup).where(KBGroup.tenant_id == current_user.tenant_id)
    )
    return [{"id": str(g.id), "name": g.name, "category": g.category, "is_active": g.is_active}
            for g in result.scalars().all()]


@router.post("/groups")
async def create_group(body: dict, current_user: CurrentUser, db: DB):
    _require_manager(current_user)
    g = KBGroup(
        tenant_id=current_user.tenant_id,
        name=body["name"],
        category=body.get("category", "general"),
        positioning=body.get("positioning", []),
        email_types=body.get("email_types", []),
    )
    db.add(g)
    await db.commit()
    return {"id": str(g.id)}


@router.get("/documents")
async def list_documents(current_user: CurrentUser, db: DB, group_id: str | None = None):
    q = select(KBDocument).where(KBDocument.tenant_id == current_user.tenant_id)
    if group_id:
        q = q.where(KBDocument.group_id == uuid.UUID(group_id))
    result = await db.execute(q)
    docs = result.scalars().all()
    return [{"id": str(d.id), "title": d.title, "source_type": d.source_type,
             "status": d.status, "chunk_count": d.chunk_count} for d in docs]


@router.post("/documents")
async def upload_document(
    current_user: CurrentUser,
    db: DB,
    group_id: str = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
):
    _require_manager(current_user)
    import os
    from app.config import settings as app_settings
    content = await file.read()
    storage_dir = os.path.join(app_settings.STORAGE_PATH, str(current_user.tenant_id), "kb")
    os.makedirs(storage_dir, exist_ok=True)
    file_path = os.path.join(storage_dir, f"{uuid.uuid4()}_{file.filename}")
    with open(file_path, "wb") as f:
        f.write(content)

    doc = KBDocument(
        tenant_id=current_user.tenant_id,
        group_id=uuid.UUID(group_id),
        title=title,
        source_type=file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "txt",
        storage_path=file_path,
        status="processing",
        created_by=current_user.id,
    )
    db.add(doc)
    await db.commit()

    # Enqueue background ingestion
    from app.worker.tasks import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("ingest_document", str(doc.id), content)

    return {"id": str(doc.id), "status": "processing"}


@router.post("/documents/manual")
async def create_manual_document(body: dict, current_user: CurrentUser, db: DB):
    _require_manager(current_user)
    doc = KBDocument(
        tenant_id=current_user.tenant_id,
        group_id=uuid.UUID(body["group_id"]),
        title=body["title"],
        source_type="manual",
        status="processing",
        created_by=current_user.id,
    )
    db.add(doc)
    await db.commit()

    content = body.get("content", "").encode()
    from app.worker.tasks import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("ingest_document", str(doc.id), content)
    return {"id": str(doc.id)}
