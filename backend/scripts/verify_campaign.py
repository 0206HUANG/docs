"""
Verify outbound campaign + SOP follow-ups + reply-stop.

Creates a running campaign (2 SOP steps, 0h interval so both fire immediately)
sent from the Gmail account to two recipients:
  - bosheng@graduate.utm.my : gets the first-touch email, then we simulate a
    reply → SOP stops (status=replied, step=1)
  - yihu73385@gmail.com      : never replies → gets first-touch + follow-up
    (status=completed, step=2)

    python scripts/verify_campaign.py
"""
import asyncio
import uuid

from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models import Campaign, CampaignRecipient, EmailAccount, Tenant
from app.services.campaign import mark_replied, run_due_recipients

DOMAIN = "demo.emailai.local"
GMAIL = "yihu73385@gmail.com"
BOSHENG = "bosheng@graduate.utm.my"


async def status_map(cid):
    async with AsyncSessionLocal() as db:
        recips = (await db.execute(
            select(CampaignRecipient).where(CampaignRecipient.campaign_id == cid)
        )).scalars().all()
        return {r.email: (r.current_step, r.status) for r in recips}


async def main():
    async with AsyncSessionLocal() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.domain == DOMAIN))).scalar_one()
        tid = tenant.id
        acct = (await db.execute(
            select(EmailAccount).where(EmailAccount.tenant_id == tid, EmailAccount.email_address == GMAIL)
        )).scalar_one_or_none()
        if not acct:
            print("✗ 未找到 Gmail 账号,请先运行 setup_gmail.py")
            return

        c = Campaign(
            id=uuid.uuid4(), tenant_id=tid, account_id=acct.id,
            name="客户开发-测试",
            subject_template="您好 {name}，关于产品合作的洽谈",
            body_template="{name} 您好，\n\n我们是XX科技，为企业提供邮件AI自动化解决方案。"
                          "了解到贵司业务，想探讨潜在的合作机会，期待您的回复！\n\nXX团队",
            sop_steps=2, sop_interval_hours=0, status="running",
        )
        db.add(c)
        await db.flush()
        cid = c.id
        db.add(CampaignRecipient(id=uuid.uuid4(), tenant_id=tid, campaign_id=cid, email=BOSHENG, name="Bosheng"))
        db.add(CampaignRecipient(id=uuid.uuid4(), tenant_id=tid, campaign_id=cid, email=GMAIL, name="内部测试"))
        await db.commit()
    print(f"✓ 创建活动(sop_steps=2)· 收件人: {BOSHENG}, {GMAIL}")

    print("\n── 第 1 轮 SOP:群发首封开发信 ──")
    async with AsyncSessionLocal() as db:
        n1 = await run_due_recipients(db)
    print(f"  发送 {n1} 封 · 状态: {await status_map(cid)}")

    print("\n── 模拟 bosheng 回复(触发回复检测)──")
    async with AsyncSessionLocal() as db:
        k = await mark_replied(db, tid, BOSHENG)
        await db.commit()
    print(f"  {k} 个收件人标记为『已回复』")

    print("\n── 第 2 轮 SOP:未回复者继续跟进,已回复者停止 ──")
    async with AsyncSessionLocal() as db:
        n2 = await run_due_recipients(db)
    print(f"  发送 {n2} 封")

    final = await status_map(cid)
    print("\n" + "═" * 72)
    b = final.get(BOSHENG)
    i = final.get(GMAIL)
    print(f"  {BOSHENG}: step={b[0]}, status={b[1]}  (期望 step=1 replied — 回复后停止 SOP)")
    print(f"  {GMAIL}: step={i[0]}, status={i[1]}  (期望 step=2 completed — 未回复,连发 2 封)")
    ok = b and b[1] == "replied" and i and i[1] == "completed"
    print("═" * 72)
    print("✅ 主动发件 + SOP 跟进 + 回复自动停止 验证通过" if ok else "⚠️ 请检查 SOP 逻辑")
    print(f"\n📬 请去 {BOSHENG} 收件箱查看收到的客户开发信")


if __name__ == "__main__":
    asyncio.run(main())
