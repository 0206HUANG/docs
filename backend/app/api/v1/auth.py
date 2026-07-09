import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DB
from app.core.exceptions import UnauthorizedError
from app.core.permissions import RoleName
from app.core.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.db.models import User, UserRole

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str
    tenant_id: str  # UUID string


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DB):
    result = await db.execute(
        select(User)
        .where(
            User.email == body.email,
            User.tenant_id == uuid.UUID(body.tenant_id),
            User.is_active == True,
        )
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_pw):
        raise UnauthorizedError("Invalid credentials")

    payload = {"sub": str(user.id), "tid": str(user.tenant_id)}
    return TokenResponse(
        access_token=create_access_token(payload),
        refresh_token=create_refresh_token(payload),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: dict, db: DB):
    token = body.get("refresh_token", "")
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            raise UnauthorizedError()
    except Exception:
        raise UnauthorizedError("Invalid refresh token")
    data = {"sub": payload["sub"], "tid": payload["tid"]}
    return TokenResponse(
        access_token=create_access_token(data),
        refresh_token=create_refresh_token(data),
    )


@router.get("/me")
async def me(current_user: CurrentUser):
    roles = [ur.role.name for ur in current_user.user_roles]
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.name,
        "tenant_id": str(current_user.tenant_id),
        "roles": roles,
    }
