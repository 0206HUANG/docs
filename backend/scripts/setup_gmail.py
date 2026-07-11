"""
Real-Gmail end-to-end closed loop.

Configures the Gmail account, sends a simulated customer email to itself over
SMTP, triggers poll_inbox for a REAL IMAP fetch, lets the worker classify +
RAG + generate a reply, then sends that AI reply back to the inbox — so the
Gmail account visibly receives the AI-generated response.

    GMAIL_APP_PW="xxxxxxxxxxxxxxxx" python scripts/setup_gmail.py
"""
import asyncio
import os
import sys
import uuid

from sqlalchemy import select

from app.core.security import encrypt_value
from app.db.base import AsyncSessionLocal
from app.db.models import (
    AuditLog, Email, EmailAccount, EmailClassification, EmailReply, Ticket, Tenant,
)
from app.services.mail.base import OutboundEmail
from app.services.mail.imap_smtp import IMAPSMTPProvider

GMAIL = "yihu73385@gmail.com"
DOMAIN = "demo.emailai.local"

STAGE_CN = {
    "sensitive_blocked": "敏感词拦截", "classified": "分类完成", "rag_retrieved": "知识库检索",
    "reply_generated": "生成回复", "draft_created": "草稿待审", "sent": "已发送",
    "human_routed": "转人工", "skipped": "跳过",
}


async def main():
    pw = os.environ.get("GMAIL_APP_PW")
    if not pw:
        print("ERROR: set GMAIL_APP_PW", file=sys.stderr)
        sys.exit(1)
    pw = pw.replace(" ", "")

    # 1. Configure / upsert the Gmail account (active, sales positioning)
    async with AsyncSessionLocal() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.domain == DOMAIN))).scalar_one()
        tid = tenant.id
        acct = (await db.execute(select(EmailAccount).where(
            EmailAccount.tenant_id == tid, EmailAccount.email_address == GMAIL
        ))).scalar_one_or_none()
        if not acct:
            acct = EmailAccount(id=uuid.uuid4(), tenant_id=tid, email_address=GMAIL)
            db.add(acct)
        acct.display_name = "Demo Sales (Gmail)"
        acct.provider = "gmail"
        acct.imap_host, acct.imap_port, acct.imap_ssl = "imap.gmail.com", 993, True
        acct.smtp_host, acct.smtp_port, acct.smtp_ssl = "smtp.gmail.com", 465, True
        acct.username = GMAIL
        acct.password_enc = encrypt_value(pw)
        acct.positioning = "sales"
        acct.is_active = True
        acct.sync_status = "idle"
        acct.last_synced_at = None
        await db.commit()
        aid = str(acct.id)
    print("✓ Gmail 账号已配置 (positioning=sales, is_active=True)")

    prov = IMAPSMTPProvider("imap.gmail.com", 993, True, "smtp.gmail.com", 465, True, GMAIL, pw)

    # 2. Test IMAP login
    print("\n🔌 测试 IMAP 连接...")
    if not await prov.test_connection():
        print("✗ IMAP 连接失败。请确认已在 Gmail 设置里【启用 IMAP】(第3步),或应用专用密码是否正确。")
        return
    print("✓ IMAP 连接成功")

    # 3. Send a simulated customer email to self over SMTP
    subj = f"产品规格与价格咨询-{uuid.uuid4().hex[:6]}"
    print(f"\n📤 用 SMTP 发送模拟客户邮件到 {GMAIL} ...")
    try:
        await prov.send(OutboundEmail(
            from_addr=GMAIL, from_name="采购李经理", to_addrs=[GMAIL], cc_addrs=[],
            subject=subj,
            body_text="你好，我们计划采购贵公司产品。请问标准版和专业版有什么区别？"
                      "价格和交货期分别是多少？希望尽快答复，谢谢。",
        ))
        print(f"✓ 已发送: {subj}")
    except Exception as e:
        print(f"✗ SMTP 发送失败: {type(e).__name__}: {e}")
        return

    print("\n⏳ 等待邮件送达 Gmail...")
    await asyncio.sleep(8)

    # 4. Trigger a REAL poll_inbox on the worker
    from app.worker.tasks import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("poll_inbox", aid)
    print("📨 已触发 poll_inbox，worker 正在真实收信 + 处理...")

    # 5. Poll until the worker has classified our email
    email_id = None
    cls = None
    for i in range(40):
        await asyncio.sleep(2)
        async with AsyncSessionLocal() as db:
            em = (await db.execute(
                select(Email).where(Email.tenant_id == tid, Email.subject == subj)
            )).scalar_one_or_none()
            if em:
                email_id = em.id
                cls = (await db.execute(
                    select(EmailClassification).where(EmailClassification.email_id == em.id)
                )).scalar_one_or_none()
                if cls:
                    print(f"✓ worker 已完成处理 (~{(i + 1) * 2}s)")
                    break
        if i == 12 and not email_id:
            print("  (仍在收信,IMAP 可能稍慢...)")
    if not cls:
        where = "收到但未分类(查 worker 日志)" if email_id else "未收到(检查 IMAP 是否启用)"
        print(f"✗ 超时:邮件{where}")
        return

    # 6. Show what the worker persisted
    async with AsyncSessionLocal() as db:
        cls = (await db.execute(select(EmailClassification).where(EmailClassification.email_id == email_id))).scalar_one()
        reply = (await db.execute(select(EmailReply).where(EmailReply.email_id == email_id))).scalar_one_or_none()
        ticket = (await db.execute(select(Ticket).where(Ticket.email_id == email_id))).scalar_one_or_none()
        audits = (await db.execute(
            select(AuditLog).where(AuditLog.email_id == email_id).order_by(AuditLog.created_at)
        )).scalars().all()

    print("\n" + "═" * 72)
    print("📊 真实 Gmail 邮件处理结果")
    print("═" * 72)
    print(f"🧠 分类: {cls.email_type} · 语言={cls.language} · 紧急度={cls.urgency} · 模型={cls.llm_model}")
    print("\n🔗 处理链路:")
    for a in audits:
        print(f"   {'✓' if a.status == 'success' else '✗'} {STAGE_CN.get(a.stage, a.stage)}")
    if ticket:
        print(f"\n🎫 工单: {ticket.title} · 优先级{ticket.priority}")
    if reply:
        print(f"\n✍️  AI 生成回复 (草稿, {reply.llm_model}, 引用 {len(reply.rag_chunk_ids or [])} 条知识库):")
        print("   " + (reply.draft_content or "").replace("\n", "\n   "))

    # 7. Send the AI reply back to the Gmail inbox (demo auto-send)
    if reply and reply.draft_content:
        print(f"\n📤 将 AI 回复发送回 {GMAIL} (演示自动发送)...")
        await pool.enqueue_job("send_reply", str(reply.id))
        for i in range(15):
            await asyncio.sleep(2)
            async with AsyncSessionLocal() as db:
                r = (await db.execute(select(EmailReply).where(EmailReply.id == reply.id))).scalar_one()
                if r.status == "sent":
                    print(f"✓ AI 回复已发送！请去 {GMAIL} 收件箱查看 (主题: Re: {subj})")
                    break
        else:
            print("  (发送中,稍后查收 Gmail)")

    print("\n" + "═" * 72)
    print("✅ 真实 Gmail 闭环完成: SMTP发信 → IMAP收信 → worker处理 → AI回复 → 发回邮箱")


if __name__ == "__main__":
    asyncio.run(main())
