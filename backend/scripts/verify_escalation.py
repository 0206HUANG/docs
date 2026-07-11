"""
Verify overdue-ticket escalation. Creates a ticket stamped 30h in the past
(priority 2, still open), runs the escalation pass directly (what the cron
does), and checks it bumped the priority/level and notified admins.

    python scripts/verify_escalation.py
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models import Email, EmailAccount, EmailThread, Notification, Tenant, Ticket
from app.services.escalation import escalate_overdue

DOMAIN = "demo.emailai.local"


async def main():
    async with AsyncSessionLocal() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.domain == DOMAIN))).scalar_one()
        tid = tenant.id
        acct = (await db.execute(select(EmailAccount).where(EmailAccount.tenant_id == tid))).scalars().first()

        old = datetime.now(timezone.utc) - timedelta(hours=30)
        thread = EmailThread(id=uuid.uuid4(), tenant_id=tid, account_id=acct.id, subject="超时测试", status="open")
        db.add(thread)
        await db.flush()
        e = Email(
            id=uuid.uuid4(), tenant_id=tid, account_id=acct.id, thread_id=thread.id,
            message_id=f"<esc-{uuid.uuid4()}@t.test>", direction="inbound",
            from_addr="overdue@client.com", from_name="等待中的客户", to_addrs=["x"], cc_addrs=[],
            subject="紧急：等待处理", body_text="我的问题一直没人回复", received_at=old, created_at=old,
        )
        db.add(e)
        await db.flush()
        t = Ticket(
            id=uuid.uuid4(), tenant_id=tid, email_id=e.id, account_id=acct.id,
            title="[人工处理] 紧急：等待处理", reason="strategy", status="open", priority=2,
            created_at=old,
        )
        db.add(t)
        await db.commit()
        tkid = t.id
    print("✓ 建立超时工单(30 小时前, priority=2, status=open)")

    # run the escalation pass (this is exactly what the cron calls)
    async with AsyncSessionLocal() as db:
        n = await escalate_overdue(db)
    print(f"✓ 升级扫描完成,本轮共升级 {n} 个超时工单")

    async with AsyncSessionLocal() as db:
        t = (await db.execute(select(Ticket).where(Ticket.id == tkid))).scalar_one()
        notifs = (await db.execute(
            select(Notification).where(Notification.ref_type == "ticket", Notification.ref_id == tkid)
        )).scalars().all()

    print("\n" + "═" * 72)
    print("📊 超时升级结果")
    print("═" * 72)
    print(f"工单: escalation_level={t.escalation_level} · priority={t.priority}(原 2)"
          f" · last_escalated={t.last_escalated_at}")
    print(f"生成通知: {len(notifs)} 条")
    for nn in notifs:
        print(f"  → 给用户 {str(nn.user_id)[:8]}...: {nn.title}")
        print(f"     {nn.body}")
    print("═" * 72)

    ok = t.escalation_level >= 1 and len(notifs) >= 1
    print("✅ 超时升级验证通过:工单自动升级 + 通知管理员" if ok else "⚠️ 请检查升级逻辑")


if __name__ == "__main__":
    asyncio.run(main())
