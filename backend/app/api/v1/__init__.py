from fastapi import APIRouter

from app.api.v1 import auth, accounts, emails, kb, tickets, notifications, settings, reports, users, resumes, customers, campaigns, outbox, track

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
router.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
router.include_router(customers.router, prefix="/customers", tags=["customers"])
router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
router.include_router(outbox.router, prefix="/outbox", tags=["outbox"])
router.include_router(track.router, prefix="/track", tags=["tracking"])
