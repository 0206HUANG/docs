import uuid
from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import UnauthorizedError
from app.core.security import decode_token
from app.db.base import get_db
from app.db.models import User, UserRole, Role

bearer = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise UnauthorizedError("Invalid token type")
        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedError()
    except JWTError:
        raise UnauthorizedError("Invalid token")

    result = await db.execute(
        select(User)
        .where(User.id == uuid.UUID(user_id), User.is_active == True)
        .options(
            selectinload(User.user_roles).selectinload(UserRole.role)
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]
