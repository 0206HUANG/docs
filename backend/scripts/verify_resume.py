"""
Verify the resume-parsing feature end-to-end through the real worker path.

Injects a job-application email (a resume in the body), enqueues process_email,
and prints the ResumeProfile the worker extracted.

    python scripts/verify_resume.py
"""
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models import (
    AuditLog, Email, EmailAccount, EmailClassification, EmailThread, ResumeProfile, Tenant,
)

DOMAIN = "demo.emailai.local"

RESUME_BODY = """尊敬的招聘负责人，您好：

我对贵公司的高级后端工程师职位非常感兴趣，现附上我的简历，期待您的回复。

应聘岗位：高级后端工程师

姓名：李明
邮箱：liming2024@example.com
电话：138-0013-8000

教育背景：
2016.09-2020.06 清华大学 计算机科学与技术 本科
2020.09-2022.06 北京大学 软件工程 硕士

工作经历：
2022.07-2024.06 字节跳动 后端开发工程师
  负责推荐系统后端服务，使用 Python 与 Go，支撑日均十亿级请求。
2024.07-至今 美团 高级后端工程师
  主导订单系统微服务拆分与性能优化，QPS 提升 3 倍。

专业技能：Python, FastAPI, Go, PostgreSQL, Redis, Kafka, Docker, Kubernetes

期望薪资：35k-45k

谢谢！
李明
"""


async def main():
    async with AsyncSessionLocal() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.domain == DOMAIN))).scalar_one()
        tid = tenant.id
        acct = (await db.execute(
            select(EmailAccount).where(EmailAccount.tenant_id == tid, EmailAccount.positioning == "hr")
        )).scalar_one_or_none()
        if not acct:
            acct = (await db.execute(
                select(EmailAccount).where(EmailAccount.tenant_id == tid)
            )).scalars().first()

        subj = f"应聘高级后端工程师-李明-{uuid.uuid4().hex[:4]}"
        thread = EmailThread(id=uuid.uuid4(), tenant_id=tid, account_id=acct.id, subject=subj, status="open")
        db.add(thread)
        await db.flush()
        email = Email(
            id=uuid.uuid4(), tenant_id=tid, account_id=acct.id, thread_id=thread.id,
            message_id=f"<resume-{uuid.uuid4()}@job.test>", direction="inbound",
            from_addr="liming2024@example.com", from_name="李明",
            to_addrs=[acct.email_address], cc_addrs=[], subject=subj,
            body_text=RESUME_BODY,
            received_at=datetime.now(timezone.utc), created_at=datetime.now(timezone.utc),
        )
        db.add(email)
        await db.commit()
        eid = email.id
    print(f"✓ 注入简历邮件 email_id={eid} (账号定位={acct.positioning})")

    from app.worker.tasks import enqueue_process_email
    await enqueue_process_email(str(eid))
    print("📨 已投递 process_email,等待 worker 分类 + 解析简历...")

    prof = None
    for i in range(30):
        await asyncio.sleep(2)
        async with AsyncSessionLocal() as db:
            prof = (await db.execute(
                select(ResumeProfile).where(ResumeProfile.email_id == eid)
            )).scalar_one_or_none()
            if prof:
                print(f"✓ worker 已解析 (~{(i + 1) * 2}s)")
                break

    async with AsyncSessionLocal() as db:
        cls = (await db.execute(
            select(EmailClassification).where(EmailClassification.email_id == eid)
        )).scalar_one_or_none()
        audits = (await db.execute(
            select(AuditLog).where(AuditLog.email_id == eid).order_by(AuditLog.created_at)
        )).scalars().all()

    print(f"\n🧠 分类: {cls.email_type if cls else '?'} · 语言={cls.language if cls else '?'}")
    print("🔗 链路: " + " → ".join(a.stage for a in audits))

    if not prof:
        print("\n✗ 未解析出简历(邮件可能未被分类为 resume)")
        return

    print("\n" + "═" * 72)
    print("📄 简历自动解析结果 (ResumeProfile)")
    print("═" * 72)
    print(f"  姓名:      {prof.candidate_name}")
    print(f"  邮箱:      {prof.candidate_email}")
    print(f"  电话:      {prof.candidate_phone}")
    print(f"  期望岗位:  {prof.desired_position}")
    print(f"  期望薪资:  {prof.expected_salary}")
    print(f"  工作年限:  {prof.years_experience}")
    print(f"  学历:")
    for e in (prof.education or []):
        print(f"    - {e}")
    print(f"  工作经历:")
    for e in (prof.experience or []):
        print(f"    - {e}")
    print(f"  技能:      {', '.join(prof.skills or [])}")
    print(f"  匹配度:    {prof.match_score}  ({prof.match_notes})")
    print(f"  AI 评估:   {prof.summary}")
    print(f"  来源:      {prof.source} · 模型: {prof.llm_model}")
    print("\n✅ 简历自动解析验证通过:邮件 → 分类为 resume → AI 抽取结构化字段 → 入库")


if __name__ == "__main__":
    asyncio.run(main())
