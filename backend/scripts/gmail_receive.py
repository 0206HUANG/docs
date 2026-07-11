"""
Receive a REAL external email into the Gmail account, process it, reply back.

Run this AFTER an email has been sent from some OTHER mailbox to
yihu73385@gmail.com. It triggers poll_inbox (real IMAP fetch) on the worker,
waits for the pipeline to classify the new inbound message, prints the result,
then sends the AI reply back to the original sender's address.

    python scripts/gmail_receive.py
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models import (
    AuditLog, Email, EmailAccount, EmailClassification, EmailReply, Ticket, Tenant,
)
from app.worker.tasks import get_arq_pool

GMAIL = "yihu73385@gmail.com"
DOMAIN = "demo.emailai.local"
STAGE_CN = {
    "sensitive_blocked": "敏感词拦截", "classified": "分类", "rag_retrieved": "知识库检索",
    "reply_generated": "生成回复", "draft_created": "草稿待审", "sent": "已发送",
    "human_routed": "转人工", "skipped": "跳过",
}


async def main():
    async with AsyncSessionLocal() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.domain == DOMAIN))).scalar_one()
        tid = tenant.id
        acct = (await db.execute(select(EmailAccount).where(
            EmailAccount.tenant_id == tid, EmailAccount.email_address == GMAIL
        ))).scalar_one()
        aid = str(acct.id)
        # look back far enough that poll_inbox's SINCE covers today's mail
        acct.last_synced_at = None
        await db.commit()

    start = datetime.now(timezone.utc)
    pool = await get_arq_pool()
    print(f"📨 收取 {GMAIL} 收件箱的新邮件 (来自外部发件人)...")

    found = None
    for rnd in range(8):
        await pool.enqueue_job("poll_inbox", aid)
        for _ in range(5):
            await asyncio.sleep(3)
            async with AsyncSessionLocal() as db:
                ems = (await db.execute(
                    select(Email).where(
                        Email.tenant_id == tid,
                        Email.direction == "inbound",
                        Email.from_addr != GMAIL,
                        Email.created_at >= start,
                    ).order_by(Email.created_at.desc())
                )).scalars().all()
                # skip system senders (Google security alerts, mailer-daemon, etc.)
                SYS = ("no-reply", "noreply", "google.com", "mailer-daemon", "postmaster")
                em = next((e for e in ems if not any(s in (e.from_addr or "").lower() for s in SYS)), None)
                if em:
                    cls = (await db.execute(
                        select(EmailClassification).where(EmailClassification.email_id == em.id)
                    )).scalar_one_or_none()
                    if cls:
                        found = em.id
                        break
        if found:
            break
        print(f"  ...第 {rnd + 1} 轮暂未收到,重试收取")

    if not found:
        print("✗ 未收到新邮件。请确认已从【其他邮箱】(非 yihu73385)发到 yihu73385@gmail.com")
        return

    async with AsyncSessionLocal() as db:
        em = (await db.execute(select(Email).where(Email.id == found))).scalar_one()
        cls = (await db.execute(select(EmailClassification).where(EmailClassification.email_id == found))).scalar_one()
        reply = (await db.execute(select(EmailReply).where(EmailReply.email_id == found))).scalar_one_or_none()
        ticket = (await db.execute(select(Ticket).where(Ticket.email_id == found))).scalar_one_or_none()
        audits = (await db.execute(
            select(AuditLog).where(AuditLog.email_id == found).order_by(AuditLog.created_at)
        )).scalars().all()
        sender, subj = em.from_addr, em.subject

    print("\n" + "═" * 72)
    print(f"📧 真实收到邮件: {subj}")
    print(f"   来自: {em.from_name or ''} <{sender}>")
    print(f"   正文: {(em.body_text or '')[:80]}...")
    print("─" * 72)
    print(f"🧠 分类: {cls.email_type} · 语言={cls.language} · 紧急度={cls.urgency} · 模型={cls.llm_model}")
    print("🔗 链路: " + " → ".join(STAGE_CN.get(a.stage, a.stage) for a in audits))
    if ticket:
        print(f"🎫 工单: {ticket.title} · 优先级{ticket.priority}")

    if reply and reply.draft_content:
        print(f"\n✍️  AI 回复 (引用 {len(reply.rag_chunk_ids or [])} 条知识库):")
        print("   " + reply.draft_content.replace("\n", "\n   "))
        print(f"\n📤 把 AI 回复发回给 {sender} ...")
        await pool.enqueue_job("send_reply", str(reply.id))
        for _ in range(15):
            await asyncio.sleep(2)
            async with AsyncSessionLocal() as db:
                r = (await db.execute(select(EmailReply).where(EmailReply.id == reply.id))).scalar_one()
                if r.status == "sent":
                    print(f"✓ 已发送！请去 {sender} 的收件箱查看 AI 回复 (主题: Re: {subj})")
                    break
        else:
            print("  (发送中,稍后查收)")

    print("\n" + "═" * 72)
    print("✅ 真实闭环完成: 外部邮件 → IMAP 收信 → worker 处理 → AI 回复 → 发回发件人")


if __name__ == "__main__":
    asyncio.run(main())
