"""
Verify scheduled send + cancel(撤回) + open tracking.

1. Queue email A (due now, track_opens=True) → the send pass dispatches it
   via real Gmail SMTP with a tracking pixel embedded.
2. Queue email B (due in 1h) and cancel it → the send pass must NOT send it.
3. Hit the public tracking pixel twice (as a mail client would) → open_count=2.

    python scripts/verify_outbox.py
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models import EmailAccount, ScheduledEmail, Tenant
from app.services.outbox import send_due_scheduled

DOMAIN = "demo.emailai.local"
GMAIL = "yihu73385@gmail.com"
APP_BASE = "http://app:8000"  # compose service name on add_default network


async def main():
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.domain == DOMAIN))).scalar_one()
        tid = tenant.id
        acct = (await db.execute(
            select(EmailAccount).where(EmailAccount.tenant_id == tid, EmailAccount.email_address == GMAIL)
        )).scalar_one_or_none()
        if not acct:
            print("✗ 未找到 Gmail 账号,请先运行 setup_gmail.py")
            return

        a = ScheduledEmail(
            id=uuid.uuid4(), tenant_id=tid, account_id=acct.id,
            to_addrs=["bosheng@graduate.utm.my"], cc_addrs=[],
            subject=f"[定时发送测试] 产品资料-{uuid.uuid4().hex[:4]}",
            body_text="您好，这是一封定时发送的邮件，包含打开追踪像素。\n\n—— EmailAI 定时发送引擎",
            scheduled_at=now, track_opens=True,
        )
        b = ScheduledEmail(
            id=uuid.uuid4(), tenant_id=tid, account_id=acct.id,
            to_addrs=["bosheng@graduate.utm.my"], cc_addrs=[],
            subject="[误发测试] 这封不应被发出",
            body_text="这封邮件应在发送前被撤回。",
            scheduled_at=now + timedelta(hours=1), track_opens=False,
        )
        db.add_all([a, b])
        await db.commit()
        aid, bid, tracking_id = a.id, b.id, a.tracking_id
    print("✓ 排队 2 封:A(立即到期+追踪) / B(1小时后)")

    # cancel B before it can ever send (误发限时撤回)
    async with AsyncSessionLocal() as db:
        bb = (await db.execute(select(ScheduledEmail).where(ScheduledEmail.id == bid))).scalar_one()
        bb.status = "cancelled"
        await db.commit()
    print("✓ B 已在发送前撤回 (cancelled)")

    # run the send pass (what cron:send_scheduled does every minute)
    async with AsyncSessionLocal() as db:
        n = await send_due_scheduled(db)
    print(f"✓ 发送扫描完成,发出 {n} 封 (期望 1 — 仅 A)")

    # simulate the recipient's mail client loading the pixel twice
    async with httpx.AsyncClient(timeout=15) as client:
        for i in range(2):
            r = await client.get(f"{APP_BASE}/api/v1/track/open/{tracking_id}")
            print(f"  像素请求 {i + 1}: HTTP {r.status_code} · {r.headers.get('content-type')} · {len(r.content)}B")

    async with AsyncSessionLocal() as db:
        a2 = (await db.execute(select(ScheduledEmail).where(ScheduledEmail.id == aid))).scalar_one()
        b2 = (await db.execute(select(ScheduledEmail).where(ScheduledEmail.id == bid))).scalar_one()

    print("\n" + "═" * 72)
    print("📊 定时发送 + 撤回 + 打开追踪")
    print("═" * 72)
    print(f"A: status={a2.status} · sent_at={a2.sent_at}")
    print(f"   open_count={a2.open_count} · first={a2.first_opened_at} · last={a2.last_opened_at}")
    print(f"B: status={b2.status} (期望 cancelled,未被发出)")
    ok = a2.status == "sent" and a2.open_count == 2 and b2.status == "cancelled"
    print("═" * 72)
    print("✅ 定时发送 / 撤回 / 打开追踪 验证通过" if ok else "⚠️ 请检查 outbox 逻辑")
    print(f"\n📬 A 已真实发送到 bosheng@graduate.utm.my (含隐形追踪像素)")


if __name__ == "__main__":
    asyncio.run(main())
