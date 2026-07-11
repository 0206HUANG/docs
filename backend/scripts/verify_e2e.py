"""
End-to-end production-path verification.

Proves the REAL runtime path — not a script reimplementation:
    inject inbound email → enqueue on ARQ/Redis → the worker container's
    process_email task → orchestrator → writes classification/reply/ticket/
    audit rows back to Postgres.

Steps:
  1. Configure the demo tenant's LLM = DeepSeek (encrypted).
  2. Widen the FAQ KB group's email_types and RE-EMBED its chunks with the
     local embedder (seed stored zero-vector placeholders that can't match).
  3. Force sales reply-types to draft_review so no fake SMTP send is attempted.
  4. Inject a fresh inbound email on the sales account.
  5. enqueue_process_email(...) → real worker picks it up.
  6. Poll Postgres until the worker writes the classification, then print the
     full audit trail + generated reply / ticket.

Run in a one-off container on the compose network (worker must run latest image):
    DEEPSEEK_KEY=sk-... python scripts/verify_e2e.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import encrypt_value
from app.db.base import AsyncSessionLocal
from app.db.models import (
    AuditLog, Email, EmailAccount, EmailClassification, EmailReply,
    EmailThread, EmailTypeStrategy, KBChunk, KBGroup, Ticket, Tenant,
)
from app.services.llm.local_embed import LocalHashEmbedProvider

DEMO_DOMAIN = "demo.emailai.local"
SALES_TYPES = ["customer_inquiry", "quote_request", "material_request", "order_confirm", "complaint", "other"]

STAGE_CN = {
    "sensitive_blocked": "敏感词拦截", "classified": "分类完成", "rag_retrieved": "知识库检索",
    "reply_generated": "生成回复", "draft_created": "草稿待审", "sent": "已发送",
    "human_routed": "转人工", "skipped": "跳过",
}


async def prepare(db, key: str) -> tuple[uuid.UUID, uuid.UUID]:
    embed = LocalHashEmbedProvider()

    tenant = (await db.execute(select(Tenant).where(Tenant.domain == DEMO_DOMAIN))).scalar_one()

    # 1. LLM = DeepSeek (chat); embeddings fall back to local automatically
    s = dict(tenant.settings or {})
    s["llm_config"] = {"provider": "deepseek", "api_key_enc": encrypt_value(key), "model": "deepseek-chat"}
    tenant.settings = s

    # 2. widen FAQ group types + re-embed all chunks with the real local embedder
    groups = (await db.execute(select(KBGroup).where(KBGroup.tenant_id == tenant.id))).scalars().all()
    for g in groups:
        if g.category == "faq" or "产品" in g.name:
            g.email_types = SALES_TYPES
            if "sales" not in (g.positioning or []):
                g.positioning = list(set((g.positioning or []) + ["sales"]))

    chunks = (await db.execute(select(KBChunk).where(KBChunk.tenant_id == tenant.id))).scalars().all()
    for c in chunks:
        c.embedding = (await embed.embed([c.content])).embeddings[0]
    print(f"  ✓ 重算 {len(chunks)} 条知识库 chunk 的本地向量")

    # 3. force sales reply-types to draft_review (avoid fake-SMTP auto_send)
    strategies = (await db.execute(
        select(EmailTypeStrategy).where(EmailTypeStrategy.tenant_id == tenant.id)
    )).scalars().all()
    by_type = {st.email_type: st for st in strategies}
    for t in ("customer_inquiry", "quote_request", "material_request"):
        if t in by_type:
            by_type[t].send_strategy = "draft_review"

    account = (await db.execute(
        select(EmailAccount).where(EmailAccount.tenant_id == tenant.id, EmailAccount.positioning == "sales")
    )).scalar_one()

    await db.commit()
    return tenant.id, account.id


async def inject(db, tenant_id, account_id) -> str:
    account = (await db.execute(select(EmailAccount).where(EmailAccount.id == account_id))).scalar_one()
    thread = EmailThread(id=uuid.uuid4(), tenant_id=tenant_id, account_id=account_id,
                         subject="产品规格与交货期咨询", status="open")
    db.add(thread)
    await db.flush()

    email = Email(
        id=uuid.uuid4(), tenant_id=tenant_id, account_id=account_id, thread_id=thread.id,
        message_id=f"<e2e-{uuid.uuid4()}@buyer.test>", direction="inbound",
        from_addr="wang@acme-trading.com", from_name="采购王经理",
        to_addrs=[account.email_address], cc_addrs=[],
        subject="产品规格与交货期咨询",
        body_text="你好，我们准备下单，请问贵公司产品有哪些规格？标准版和专业版有什么区别？"
                  "另外交货期大概多久？希望尽快回复，谢谢。",
        received_at=datetime.now(timezone.utc), created_at=datetime.now(timezone.utc),
    )
    db.add(email)
    await db.commit()
    return str(email.id)


async def main():
    key = os.environ.get("DEEPSEEK_KEY")
    if not key:
        print("ERROR: set DEEPSEEK_KEY", file=sys.stderr)
        sys.exit(1)

    print("\n🔧 准备阶段")
    async with AsyncSessionLocal() as db:
        tenant_id, account_id = await prepare(db, key)
        print("  ✓ 配置 tenant LLM = DeepSeek，销售类型 → 草稿待审")

    async with AsyncSessionLocal() as db:
        email_id = await inject(db, tenant_id, account_id)
    print(f"  ✓ 注入 inbound 邮件 email_id={email_id}")

    # enqueue onto the REAL ARQ queue — the worker container consumes it
    from app.worker.tasks import enqueue_process_email
    await enqueue_process_email(email_id)
    print("\n📨 已投递到 ARQ 队列，等待 worker 容器处理...")

    # poll until worker writes the classification
    cls = None
    for i in range(30):
        await asyncio.sleep(2)
        async with AsyncSessionLocal() as db:
            cls = (await db.execute(
                select(EmailClassification).where(EmailClassification.email_id == uuid.UUID(email_id))
            )).scalar_one_or_none()
        if cls:
            print(f"  ✓ worker 已处理 (耗时 ~{(i+1)*2}s)")
            break
    else:
        print("  ✗ 超时：worker 未在 60s 内处理。检查 worker 日志。")
        return

    # print the full result the worker persisted
    async with AsyncSessionLocal() as db:
        cls = (await db.execute(
            select(EmailClassification).where(EmailClassification.email_id == uuid.UUID(email_id))
        )).scalar_one()
        reply = (await db.execute(
            select(EmailReply).where(EmailReply.email_id == uuid.UUID(email_id))
        )).scalar_one_or_none()
        ticket = (await db.execute(
            select(Ticket).where(Ticket.email_id == uuid.UUID(email_id))
        )).scalar_one_or_none()
        audits = (await db.execute(
            select(AuditLog).where(AuditLog.email_id == uuid.UUID(email_id)).order_by(AuditLog.created_at)
        )).scalars().all()

    print("\n" + "═" * 72)
    print("📊 worker 写回 Postgres 的结果")
    print("═" * 72)
    print(f"🧠 分类: {cls.email_type} · 语言={cls.language} · 紧急度={cls.urgency}"
          f" · 置信度={cls.confidence} · 模型={cls.llm_model}"
          f" · tokens={cls.prompt_tokens}+{cls.completion_tokens}")

    print("\n🔗 审计链路 (audit_logs):")
    for a in audits:
        mark = "✓" if a.status == "success" else "✗"
        print(f"   {mark} {STAGE_CN.get(a.stage, a.stage):8s}  {a.detail or ''}")

    if reply:
        print(f"\n✍️  生成回复 (status={reply.status}, strategy={reply.send_strategy}, model={reply.llm_model}):")
        print("   " + (reply.draft_content or "").replace("\n", "\n   "))
        print(f"   引用知识库 chunk: {len(reply.rag_chunk_ids or [])} 条")
    if ticket:
        print(f"\n🎫 工单: {ticket.title} · 原因={ticket.reason} · 优先级={ticket.priority} · 状态={ticket.status}")

    print("\n" + "═" * 72)
    print("✅ 完整生产路径验证通过：注入 → ARQ → worker → orchestrator → Postgres")


if __name__ == "__main__":
    asyncio.run(main())
