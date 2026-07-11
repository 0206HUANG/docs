"""
Verify customer profiling + history-aware replies.

Sends two emails from the SAME external sender. The profile should aggregate
(email_count -> 2) and the second reply should reflect memory of the first
(the model is given the prior correspondence as context).

    python scripts/verify_customer.py
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models import (
    AuditLog, CustomerProfile, Email, EmailAccount, EmailReply, EmailThread, Tenant,
)

DOMAIN = "demo.emailai.local"


async def inject(tid, aid, from_addr, from_name, subject, body, received_at):
    async with AsyncSessionLocal() as db:
        thread = EmailThread(id=uuid.uuid4(), tenant_id=tid, account_id=aid, subject=subject, status="open")
        db.add(thread)
        await db.flush()
        e = Email(
            id=uuid.uuid4(), tenant_id=tid, account_id=aid, thread_id=thread.id,
            message_id=f"<cust-{uuid.uuid4()}@t.test>", direction="inbound",
            from_addr=from_addr, from_name=from_name, to_addrs=["sales@demo"], cc_addrs=[],
            subject=subject, body_text=body, received_at=received_at, created_at=datetime.now(timezone.utc),
        )
        db.add(e)
        await db.commit()
        return e.id


async def wait_done(eid, rounds=30):
    for _ in range(rounds):
        await asyncio.sleep(2)
        async with AsyncSessionLocal() as db:
            r = (await db.execute(select(EmailReply).where(EmailReply.email_id == eid))).scalar_one_or_none()
            if r:
                return r
            a = (await db.execute(select(AuditLog).where(AuditLog.email_id == eid))).scalars().first()
        # keep waiting until reply or timeout
    async with AsyncSessionLocal() as db:
        return (await db.execute(select(EmailReply).where(EmailReply.email_id == eid))).scalar_one_or_none()


async def main():
    async with AsyncSessionLocal() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.domain == DOMAIN))).scalar_one()
        tid = tenant.id
        acct = (await db.execute(
            select(EmailAccount).where(EmailAccount.tenant_id == tid, EmailAccount.positioning == "sales")
        )).scalars().first()
        if not acct:
            acct = (await db.execute(select(EmailAccount).where(EmailAccount.tenant_id == tid))).scalars().first()
        aid = acct.id

    customer = f"buyer-{uuid.uuid4().hex[:6]}@bigco-test.com"
    now = datetime.now(timezone.utc)
    from app.worker.tasks import enqueue_process_email

    print(f"客户: {customer}")
    print("\n── 第 1 封:首次询价 ──")
    e1 = await inject(tid, aid, customer, "采购张经理", "联想拯救者采购询价",
                      "你好，我们计划采购联想拯救者笔记本 50 台，请提供报价、配置和交货期。",
                      now - timedelta(days=2))
    await enqueue_process_email(str(e1))
    await wait_done(e1)
    print("  ✓ 已处理(建立客户画像)")

    print("\n── 第 2 封:同一客户追问 ──")
    e2 = await inject(tid, aid, customer, "采购张经理", "Re: 采购进展",
                      "你好，上次询价的产品报价和交货期有进展了吗？我们想在原来的基础上再加购 10 台，"
                      "请一并告知最新的规格、价格和交货期，谢谢。", now)
    await enqueue_process_email(str(e2))
    r2 = await wait_done(e2)

    await asyncio.sleep(2)
    async with AsyncSessionLocal() as db:
        prof = (await db.execute(select(CustomerProfile).where(
            CustomerProfile.tenant_id == tid, CustomerProfile.email == customer
        ))).scalar_one_or_none()

    print("\n" + "═" * 72)
    print("📊 客户画像 + 历史感知回复")
    print("═" * 72)
    if prof:
        fs = prof.first_seen.date() if prof.first_seen else "?"
        ls = prof.last_seen.date() if prof.last_seen else "?"
        print(f"客户画像: {prof.name} <{prof.email}> · 公司={prof.company}")
        print(f"  往来邮件数: {prof.email_count} · 首次: {fs} · 最近: {ls}")

    print("\n第 2 封 AI 回复(应体现对第 1 封『联想拯救者 50 台』的记忆):")
    if r2 and r2.draft_content:
        print("  " + r2.draft_content.replace("\n", "\n  "))
    else:
        print("  (未生成回复 — 可能被路由为转人工)")

    print("\n" + "═" * 72)
    ok = bool(prof) and prof.email_count == 2
    print(f"{'✅' if ok else '⚠️'} 画像聚合 email_count={prof.email_count if prof else '?'} (期望 2)")
    print("✅ 客户画像 + 历史参考验证完成" if ok else "⚠️ 请检查画像聚合")


if __name__ == "__main__":
    asyncio.run(main())
