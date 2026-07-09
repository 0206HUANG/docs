import uuid
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DB
from app.core.exceptions import NotFoundError, PermissionError
from app.core.permissions import RoleName, role_level
from app.core.security import encrypt_value
from app.db.models import EmailAccount

router = APIRouter()


class AccountBody(BaseModel):
    email_address: str
    display_name: str | None = None
    provider: str = "generic"
    imap_host: str
    imap_port: int = 993
    imap_ssl: bool = True
    smtp_host: str
    smtp_port: int = 465
    smtp_ssl: bool = True
    username: str
    password: str
    positioning: str = "general"
    department_id: str | None = None


def _require_admin(current_user):
    if max((role_level(ur.role.name) for ur in current_user.user_roles), default=0) < role_level(RoleName.TENANT_ADMIN):
        raise PermissionError()


@router.get("")
async def list_accounts(current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(EmailAccount).where(EmailAccount.tenant_id == current_user.tenant_id)
    )
    accounts = result.scalars().all()
    return [
        {
            "id": str(a.id), "email_address": a.email_address,
            "display_name": a.display_name, "positioning": a.positioning,
            "is_active": a.is_active, "sync_status": a.sync_status,
            "last_synced_at": a.last_synced_at.isoformat() if a.last_synced_at else None,
        }
        for a in accounts
    ]


@router.post("")
async def create_account(body: AccountBody, current_user: CurrentUser, db: DB):
    _require_admin(current_user)
    account = EmailAccount(
        tenant_id=current_user.tenant_id,
        department_id=uuid.UUID(body.department_id) if body.department_id else None,
        email_address=body.email_address,
        display_name=body.display_name,
        provider=body.provider,
        imap_host=body.imap_host,
        imap_port=body.imap_port,
        imap_ssl=body.imap_ssl,
        smtp_host=body.smtp_host,
        smtp_port=body.smtp_port,
        smtp_ssl=body.smtp_ssl,
        username=body.username,
        password_enc=encrypt_value(body.password),
        positioning=body.positioning,
    )
    db.add(account)
    await db.commit()
    return {"id": str(account.id), "email_address": account.email_address}


@router.post("/{account_id}/test")
async def test_account(account_id: str, current_user: CurrentUser, db: DB):
    _require_admin(current_user)
    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.id == uuid.UUID(account_id),
            EmailAccount.tenant_id == current_user.tenant_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise NotFoundError("EmailAccount")
    from app.services.mail import get_mail_provider
    provider = get_mail_provider(account)
    ok = await provider.test_connection()
    return {"success": ok}


@router.post("/{account_id}/toggle")
async def toggle_account(account_id: str, current_user: CurrentUser, db: DB):
    _require_admin(current_user)
    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.id == uuid.UUID(account_id),
            EmailAccount.tenant_id == current_user.tenant_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise NotFoundError("EmailAccount")
    account.is_active = not account.is_active
    await db.commit()
    return {"is_active": account.is_active}


@router.delete("/{account_id}")
async def delete_account(account_id: str, current_user: CurrentUser, db: DB):
    _require_admin(current_user)
    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.id == uuid.UUID(account_id),
            EmailAccount.tenant_id == current_user.tenant_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise NotFoundError("EmailAccount")
    await db.delete(account)
    await db.commit()
    return {"deleted": True}
