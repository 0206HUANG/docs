from fastapi import APIRouter

from app.api.v1 import auth, accounts, emails, kb, tickets, notifications, settings, reports, users

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
router.include_router(emails.router, prefix="/emails", tags=["emails"])
router.include_router(kb.router, prefix="/kb", tags=["knowledge-base"])
router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
router.include_router(settings.router, prefix="/settings", tags=["settings"])
router.include_router(reports.router, prefix="/reports", tags=["reports"])
