from enum import StrEnum
from functools import wraps
from typing import Callable
import uuid

from app.core.exceptions import PermissionError


class RoleName(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    TENANT_ADMIN = "TENANT_ADMIN"
    DEPT_MANAGER = "DEPT_MANAGER"
    MEMBER = "MEMBER"


ROLE_HIERARCHY = {
    RoleName.SUPER_ADMIN: 100,
    RoleName.TENANT_ADMIN: 80,
    RoleName.DEPT_MANAGER: 60,
    RoleName.MEMBER: 40,
}


def role_level(role_name: str) -> int:
    return ROLE_HIERARCHY.get(role_name, 0)


def require_role(minimum_role: RoleName):
    """Dependency-injectable permission guard."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, current_user=None, **kwargs):
            if current_user is None:
                raise PermissionError("Authentication required")
            user_max = max(
                (role_level(ur.role.name) for ur in current_user.user_roles),
                default=0,
            )
            if user_max < role_level(minimum_role):
                raise PermissionError(
                    f"Role '{minimum_role}' or higher required"
                )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator


def assert_same_tenant(resource_tenant_id: uuid.UUID, user_tenant_id: uuid.UUID) -> None:
    if resource_tenant_id != user_tenant_id:
        raise PermissionError("Cross-tenant access denied")
