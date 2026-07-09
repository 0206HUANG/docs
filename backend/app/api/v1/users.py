import uuid
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DB
from app.core.exceptions import PermissionError
from app.core.permissions import RoleName, role_level
from app.core.security import hash_password
from app.db.models import Department, Role, User, UserRole

router = APIRouter()


class CreateUserBody(BaseModel):
    email: str
    name: str
    password: str
    role_name: str = "MEMBER"
    department_id: str | None = None


def _require_admin(current_user):
    max_level = max((role_level(ur.role.name) for ur in current_user.user_roles), default=0)
    if max_level < role_level(RoleName.TENANT_ADMIN):
        raise PermissionError()


@router.get("")
async def list_users(current_user: CurrentUser, db: DB):
    _require_admin(current_user)
    result = await db.execute(
        select(User).where(User.tenant_id == current_user.tenant_id)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    users = result.scalars().all()
    return [{"id": str(u.id), "email": u.email, "name": u.name, "is_active": u.is_active,
             "roles": [ur.role.name for ur in u.user_roles]} for u in users]


@router.post("")
async def create_user(body: CreateUserBody, current_user: CurrentUser, db: DB):
    _require_admin(current_user)
    role_result = await db.execute(
        select(Role).where(Role.name == body.role_name,
                           (Role.tenant_id == current_user.tenant_id) | (Role.tenant_id == None))
    )
    role = role_result.scalar_one_or_none()
    if not role:
        raise PermissionError(f"Role {body.role_name} not found")

    user = User(
        tenant_id=current_user.tenant_id,
        email=body.email,
        name=body.name,
        hashed_pw=hash_password(body.password),
    )
    db.add(user)
    await db.flush()

    dept_id = uuid.UUID(body.department_id) if body.department_id else None
    ur = UserRole(user_id=user.id, role_id=role.id, department_id=dept_id)
    db.add(ur)
    await db.commit()
    return {"id": str(user.id), "email": user.email}


@router.get("/departments")
async def list_departments(current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(Department).where(Department.tenant_id == current_user.tenant_id)
    )
    depts = result.scalars().all()
    return [{"id": str(d.id), "name": d.name} for d in depts]


@router.post("/departments")
async def create_department(body: dict, current_user: CurrentUser, db: DB):
    _require_admin(current_user)
    dept = Department(
        tenant_id=current_user.tenant_id,
        name=body["name"],
        description=body.get("description"),
    )
    db.add(dept)
    await db.commit()
    return {"id": str(dept.id), "name": dept.name}
