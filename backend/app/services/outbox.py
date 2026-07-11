"""
Scheduled-send engine (定时发送) with open tracking.

A cron pass picks up due pending ScheduledEmail rows and sends them via the
account's SMTP. When track_opens is set, a 1x1 pixel pointing at the public
/api/v1/track/open/{tracking_id} endpoint is embedded in an HTML alternative
so opens can be counted (已发送邮件追踪).
"""
import html
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import EmailAccount, ScheduledEmail
from app.services.mail import get_mail_provider
from app.services.mail.base import OutboundEmail

logger = logging.getLogger(__name__)


def _html_with_pixel(body_text: str, tracking_id) -> str:
    paragraphs = html.escape(body_text or "").replace("\n", "<br>")
    pixel_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/v1/track/open/{tracking_id}"
    return (
        f'<div style="font-family:sans-serif;white-space:normal">{paragraphs}</div>'
        f'<img src="{pixel_url}" width="1" height="1" alt="" style="display:none">'
    )


async def send_due_scheduled(db: AsyncSession, now: datetime | None = None) -> int:
    """Send every pending scheduled email whose time has come. Returns count sent."""
    now = now or datetime.now(timezone.utc)
    result = await db.execute(
        select(ScheduledEmail).where(
            ScheduledEmail.status == "pending",
            ScheduledEmail.scheduled_at <= now,
        )
    )
    items = result.scalars().all()
    provider_cache: dict = {}
    sent = 0

    for s in items:
        if s.account_id not in provider_cache:
            acct = (await db.execute(
                select(EmailAccount).where(EmailAccount.id == s.account_id)
            )).scalar_one_or_none()
            provider_cache[s.account_id] = (acct, get_mail_provider(acct) if acct else None)
        acct, provider = provider_cache[s.account_id]
        if not provider:
            s.status = "failed"
            s.error_msg = "account not found"
            continue

        body_html = _html_with_pixel(s.body_text, s.tracking_id) if s.track_opens else None
        try:
            await provider.send(OutboundEmail(
                from_addr=acct.email_address, from_name=acct.display_name,
                to_addrs=list(s.to_addrs or []), cc_addrs=list(s.cc_addrs or []),
                subject=s.subject, body_text=s.body_text, body_html=body_html,
            ))
            s.status = "sent"
            s.sent_at = now
            sent += 1
        except Exception as e:
            logger.error("Scheduled send %s failed: %s", s.id, e)
            s.status = "failed"
            s.error_msg = str(e)[:500]

    await db.commit()
    if sent:
        logger.info("Scheduled send: %d emails dispatched", sent)
    return sent


async def record_open(db: AsyncSession, tracking_id) -> bool:
    """Bump open counters for a tracking pixel hit. Returns True if matched."""
    result = await db.execute(
        select(ScheduledEmail).where(ScheduledEmail.tracking_id == tracking_id)
    )
    s = result.scalar_one_or_none()
    if not s:
        return False
    now = datetime.now(timezone.utc)
    s.open_count = (s.open_count or 0) + 1
    if not s.first_opened_at:
        s.first_opened_at = now
    s.last_opened_at = now
    await db.commit()
    return True
