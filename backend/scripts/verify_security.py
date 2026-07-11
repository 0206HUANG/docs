"""
Verify black/white lists + phishing detection end-to-end via the worker.

Sets up a blacklist and whitelist rule, then injects three emails:
  1. blacklisted sender      → isolated (blacklisted), never classified by LLM
  2. phishing (payment scam) → phishing_blocked + high-priority ticket
  3. whitelisted client      → trusted, normal pipeline (phishing skipped)

    python scripts/verify_security.py
"""
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models import (
    AuditLog, Email, EmailAccount, EmailClassification, EmailListRule, EmailThread, Ticket, Tenant,
)

DOMAIN = "demo.emailai.local"


async def inject(tid, aid, from_addr, from_name, subject, body):
    async with AsyncSessionLocal() as db:
        thread = EmailThread(id=uuid.uuid4(), tenant_id=tid, account_id=aid, subject=subject, status="open")
        db.add(thread)
        await db.flush()
        e = Email(
            id=uuid.uuid4(), tenant_id=tid, account_id=aid, thread_id=thread.id,
            message_id=f"<sec-{uuid.uuid4()}@t.test>", direction="inbound",
            from_addr=from_addr, from_name=from_name, to_addrs=["hr@demo"], cc_addrs=[],
            subject=subject, body_text=body,
            received_at=datetime.now(timezone.utc), created_at=datetime.now(timezone.utc),
        )
        db.add(e)
        await db.commit()
        return e.id


async def wait_processed(eid, rounds=30):
    for _ in range(rounds):
        await asyncio.sleep(2)
        async with AsyncSessionLocal() as db:
            a = (await db.execute(select(AuditLog).where(AuditLog.email_id == eid))).scalars().first()
            if a:
                return True
    return False


async def show(label, eid):
    async with AsyncSessionLocal() as db:
        cls = (await db.execute(select(EmailClassification).where(EmailClassification.email_id == eid))).scalar_one_or_none()
        audits = (await db.execute(select(AuditLog).where(AuditLog.email_id == eid).order_by(AuditLog.created_at))).scalars().all()
        ticket = (await db.execute(select(Ticket).where(Ticket.email_id == eid))).scalar_one_or_none()
    print(f"\n【{label}】")
    print(f"  链路: {' → '.join(a.stage for a in audits) or '(无)'}")
    if cls:
        print(f"  分类: {cls.email_type} · 风险标记: {cls.has_sensitive}")
        if cls.sensitive_words:
            print(f"  风险原因: {cls.sensitive_words}")
    if ticket:
        print(f"  工单: {ticket.title} · 原因={ticket.reason} · 优先级={ticket.priority}")


async def main():
    async with AsyncSessionLocal() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.domain == DOMAIN))).scalar_one()
        tid = tenant.id
        acct = (await db.execute(select(EmailAccount).where(EmailAccount.tenant_id == tid))).scalars().first()
        aid = acct.id
        db.add(EmailListRule(tenant_id=tid, list_type="black", match_type="email",
                             value="spammer@baddomain.com", reason="已知垃圾发件人"))
        db.add(EmailListRule(tenant_id=tid, list_type="white", match_type="domain",
                             value="trusted-client.com", reason="重要客户"))
        await db.commit()
    print("✓ 配置黑名单 spammer@baddomain.com + 白名单域名 trusted-client.com")

    e1 = await inject(tid, aid, "spammer@baddomain.com", "促销", "限时大促", "点击链接立即领取优惠")
    e2 = await inject(tid, aid, "cfo@vendor-partner.com", "财务总监", "紧急：更新付款账号",
                      "由于内部审计，请将本月货款改为以下新账户：6222 0000 1111 2222，"
                      "请尽快付款至新账户，逾期将影响供货。")
    e3 = await inject(tid, aid, "buyer@trusted-client.com", "老客户", "产品咨询",
                      "你好，想了解一下你们产品的规格、价格和交货期，谢谢。")
    print("✓ 注入 3 封邮件(黑名单 / 钓鱼 / 白名单)")

    from app.worker.tasks import enqueue_process_email
    for eid in (e1, e2, e3):
        await enqueue_process_email(str(eid))
    print("📨 已投递,等待 worker 处理...")

    for eid in (e1, e2, e3):
        await wait_processed(eid)
    await asyncio.sleep(3)  # let whitelisted one finish its full pipeline

    print("\n" + "═" * 72)
    print("📊 处理结果")
    print("═" * 72)
    await show("黑名单发件人 → 应隔离", e1)
    await show("钓鱼邮件(付款账号变更)→ 应告警", e2)
    await show("白名单客户 → 应信任并正常回复", e3)
    print("\n" + "═" * 72)
    print("✅ 黑白名单 + 钓鱼识别验证完成")


if __name__ == "__main__":
    asyncio.run(main())
