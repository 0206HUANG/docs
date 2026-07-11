"""
Customer/correspondent profiling. Aggregates external senders by email address
and produces a compact history digest so AI replies stay consistent with past
correspondence (no re-asking known info, no contradictions).
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CustomerProfile, Email

logger = logging.getLogger(__name__)


async def upsert_customer(db: AsyncSession, tenant_id, email: str, name: str | None = None):
    """Create or bump the profile for this sender. Returns the profile or None."""
    addr = (email or "").strip().lower()
    if not addr or "@" not in addr:
        return None
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(CustomerProfile).where(
            CustomerProfile.tenant_id == tenant_id,
            CustomerProfile.email == addr,
        )
    )
    prof = result.scalar_one_or_none()
    if not prof:
        prof = CustomerProfile(
            tenant_id=tenant_id, email=addr, name=name, company=addr.split("@")[-1],
            email_count=1, first_seen=now, last_seen=now,
        )
        db.add(prof)
    else:
        prof.email_count = (prof.email_count or 0) + 1
        prof.last_seen = now
        if name and not prof.name:
            prof.name = name
    await db.flush()
    return prof


async def build_history_context(
    db: AsyncSession, tenant_id, email: str, exclude_email_id, limit: int = 5
) -> str:
    """Compact chronological digest of this sender's prior emails (empty if none)."""
    addr = (email or "").strip().lower()
    if not addr:
        return ""
    result = await db.execute(
        select(Email)
        .where(
            Email.tenant_id == tenant_id,
            func.lower(Email.from_addr) == addr,
            Email.id != exclude_email_id,
        )
        .order_by(Email.received_at.desc().nullslast())
        .limit(limit)
    )
    emails = list(result.scalars().all())
    if not emails:
        return ""
    lines = []
    for e in reversed(emails):  # chronological order
        when = e.received_at.strftime("%Y-%m-%d") if e.received_at else "?"
        body = (e.body_text or "").strip().replace("\n", " ")[:150]
        lines.append(f"[{when}] {e.subject or '(无主题)'}: {body}")
    return "\n".join(lines)
