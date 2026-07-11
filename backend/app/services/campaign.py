"""
Outbound campaign engine: proactive first-touch emails plus SOP follow-ups.

A cron pass sends the next step to every due recipient of a running campaign.
When a recipient replies (detected on inbound poll), their SOP sequence stops.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Campaign, CampaignRecipient, EmailAccount
from app.services.mail import get_mail_provider
from app.services.mail.base import OutboundEmail

logger = logging.getLogger(__name__)


def _render(template: str | None, name: str | None) -> str:
    n = name or ""
    return (template or "").replace("{{name}}", n).replace("{name}", n)


async def run_due_recipients(db: AsyncSession, now: datetime | None = None) -> int:
    """Send the next SOP step to every due recipient of a running campaign.
    Returns the number of emails sent."""
    now = now or datetime.now(timezone.utc)
    result = await db.execute(
        select(CampaignRecipient, Campaign)
        .join(Campaign, Campaign.id == CampaignRecipient.campaign_id)
        .where(
            Campaign.status == "running",
            CampaignRecipient.status.in_(["pending", "sent"]),
            (CampaignRecipient.next_send_at.is_(None)) | (CampaignRecipient.next_send_at <= now),
        )
    )
    rows = result.all()
    provider_cache: dict = {}
    sent = 0

    for r, c in rows:
        if r.current_step >= c.sop_steps:
            r.status = "completed"
            continue

        if c.account_id not in provider_cache:
            acct = (await db.execute(
                select(EmailAccount).where(EmailAccount.id == c.account_id)
            )).scalar_one_or_none()
            provider_cache[c.account_id] = (acct, get_mail_provider(acct) if acct else None)
        acct, provider = provider_cache[c.account_id]
        if not provider:
            r.status = "failed"
            continue

        subject = _render(c.subject_template, r.name)
        if r.current_step > 0:
            subject = f"[跟进 {r.current_step + 1}] {subject}"
        body = _render(c.body_template, r.name)
        try:
            await provider.send(OutboundEmail(
                from_addr=acct.email_address, from_name=acct.display_name,
                to_addrs=[r.email], cc_addrs=[], subject=subject, body_text=body,
            ))
            r.current_step += 1
            r.last_sent_at = now
            r.next_send_at = now + timedelta(hours=c.sop_interval_hours)
            r.status = "completed" if r.current_step >= c.sop_steps else "sent"
            sent += 1
        except Exception as e:
            logger.error("Campaign send to %s failed: %s", r.email, e)
            r.status = "failed"

    await db.commit()
    if sent:
        logger.info("Campaign SOP: sent %d emails", sent)
    return sent


async def mark_replied(db: AsyncSession, tenant_id, from_addr: str) -> int:
    """Stop SOP for any active recipient matching this inbound sender.
    Does NOT commit — the caller owns the transaction."""
    addr = (from_addr or "").strip().lower()
    if not addr:
        return 0
    result = await db.execute(
        select(CampaignRecipient).where(
            CampaignRecipient.tenant_id == tenant_id,
            func.lower(CampaignRecipient.email) == addr,
            CampaignRecipient.status.in_(["pending", "sent"]),
        )
    )
    recips = result.scalars().all()
    for r in recips:
        r.status = "replied"
    return len(recips)
