"""
Seed script: creates a demo tenant, two email accounts (mocked), sample KB,
default strategies, built-in sensitive words, and a demo user.
Run: python scripts/seed.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings
from app.core.security import hash_password, encrypt_value
from app.db.models import (
    Department, Email, EmailAccount, EmailClassification, EmailTypeStrategy,
    KBChunk, KBDocument, KBGroup, Role, SensitiveWord, Tenant, User, UserRole,
)

DEMO_TENANT_DOMAIN = "demo.emailai.local"
SENSITIVE_WORDS_BUILTIN = [
    "诉讼", "起诉", "律师函", "仲裁", "赔偿", "赔款", "投诉到", "曝光",
    "转账", "打款", "账号变更", "密码", "骗局", "lawsuit", "litigation",
    "compensation", "legal action", "wire transfer",
]

DEFAULT_STRATEGIES = [
    ("customer_inquiry", None, "auto_send", "business"),
    ("material_request", None, "auto_send", "business"),
    ("order_confirm", None, "auto_send", "business"),
    ("quote_request", None, "draft_review", "formal"),
    ("complaint", None, "draft_review", "formal"),
    ("partnership", None, "draft_review", "business"),
    ("supplier", None, "draft_review", "business"),
    ("resume", "hr", "draft_review", "formal"),
    ("payment_reminder", None, "human_only", "formal"),
    ("legal", None, "human_only", "formal"),
    ("spam", None, "skip", "business"),
    ("ad_no_reply", None, "skip", "business"),
    ("other", None, "draft_review", "business"),
]


async def seed(db: AsyncSession):
    # Check if already seeded
    existing = (await db.execute(select(Tenant).where(Tenant.domain == DEMO_TENANT_DOMAIN))).scalar_one_or_none()
    if existing:
        print("Already seeded, skipping.")
        return

    print("Seeding demo tenant...")

    # Tenant
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Demo Company",
        domain=DEMO_TENANT_DOMAIN,
        plan="pro",
        is_active=True,
        settings={
            "llm_config": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_key_enc": "",  # Set via env or settings UI
            },
            "default_tone": "business",
            "summary_config": {"period_types": ["daily"], "notify_emails": []},
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(tenant)
    await db.flush()

    # Departments
    sales_dept = Department(
        id=uuid.uuid4(), tenant_id=tenant.id,
        name="销售部", description="Sales department",
        created_at=datetime.now(timezone.utc),
    )
    hr_dept = Department(
        id=uuid.uuid4(), tenant_id=tenant.id,
        name="人事部", description="HR department",
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([sales_dept, hr_dept])
    await db.flush()

    # Roles
    admin_role = Role(id=uuid.uuid4(), tenant_id=tenant.id, name="TENANT_ADMIN")
    manager_role = Role(id=uuid.uuid4(), tenant_id=tenant.id, name="DEPT_MANAGER")
    member_role = Role(id=uuid.uuid4(), tenant_id=tenant.id, name="MEMBER")
    db.add_all([admin_role, manager_role, member_role])
    await db.flush()

    # Admin user
    admin = User(
        id=uuid.uuid4(), tenant_id=tenant.id,
        email="admin@demo.emailai.local",
        name="Admin User",
        hashed_pw=hash_password("Admin@123456"),
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(admin)
    await db.flush()
    db.add(UserRole(user_id=admin.id, role_id=admin_role.id, department_id=None))

    # Email accounts (no real IMAP — for demo, they won't poll)
    sales_account = EmailAccount(
        id=uuid.uuid4(), tenant_id=tenant.id,
        department_id=sales_dept.id,
        email_address="sales@demo.emailai.local",
        display_name="Demo Sales",
        provider="generic",
        imap_host="imap.demo.local",
        imap_port=993,
        imap_ssl=True,
        smtp_host="smtp.demo.local",
        smtp_port=465,
        smtp_ssl=True,
        username="sales@demo.emailai.local",
        password_enc=encrypt_value("demo-password"),
        positioning="sales",
        is_active=False,  # inactive — won't auto-poll in demo
        sync_status="idle",
        created_at=datetime.now(timezone.utc),
    )
    hr_account = EmailAccount(
        id=uuid.uuid4(), tenant_id=tenant.id,
        department_id=hr_dept.id,
        email_address="hr@demo.emailai.local",
        display_name="Demo HR",
        provider="generic",
        imap_host="imap.demo.local",
        imap_port=993,
        imap_ssl=True,
        smtp_host="smtp.demo.local",
        smtp_port=465,
        smtp_ssl=True,
        username="hr@demo.emailai.local",
        password_enc=encrypt_value("demo-password"),
        positioning="hr",
        is_active=False,
        sync_status="idle",
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([sales_account, hr_account])
    await db.flush()

    # Knowledge base groups
    faq_group = KBGroup(
        id=uuid.uuid4(), tenant_id=tenant.id,
        department_id=sales_dept.id,
        name="产品FAQ",
        category="faq",
        positioning=["sales", "support"],
        email_types=["customer_inquiry", "material_request"],
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    hr_group = KBGroup(
        id=uuid.uuid4(), tenant_id=tenant.id,
        department_id=hr_dept.id,
        name="招聘话术",
        category="hr",
        positioning=["hr"],
        email_types=["resume"],
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([faq_group, hr_group])
    await db.flush()

    # Sample KB documents (manual)
    faq_doc = KBDocument(
        id=uuid.uuid4(), tenant_id=tenant.id,
        group_id=faq_group.id,
        title="产品常见问题解答",
        source_type="manual",
        status="ready",
        chunk_count=2,
        created_by=admin.id,
        created_at=datetime.now(timezone.utc),
    )
    hr_doc = KBDocument(
        id=uuid.uuid4(), tenant_id=tenant.id,
        group_id=hr_group.id,
        title="招聘回复模板",
        source_type="manual",
        status="ready",
        chunk_count=1,
        created_by=admin.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([faq_doc, hr_doc])
    await db.flush()

    # KB chunks with placeholder embeddings (no real embedding in seed)
    zero_emb = [0.0] * 1536
    db.add(KBChunk(id=uuid.uuid4(), tenant_id=tenant.id, document_id=faq_doc.id,
                   group_id=faq_group.id, content="我们的产品提供标准版和专业版两种规格。标准版适合中小企业，支持最多10个用户。专业版支持无限用户，包含高级报表和API集成功能。",
                   chunk_index=0, embedding=zero_emb, token_count=40))
    db.add(KBChunk(id=uuid.uuid4(), tenant_id=tenant.id, document_id=faq_doc.id,
                   group_id=faq_group.id, content="产品交货期：标准配置7个工作日，定制化配置需15-30个工作日。如需加急请联系销售代表。",
                   chunk_index=1, embedding=zero_emb, token_count=30))
    db.add(KBChunk(id=uuid.uuid4(), tenant_id=tenant.id, document_id=hr_doc.id,
                   group_id=hr_group.id, content="感谢您投递简历！我们已收到您的申请，HR团队将在5个工作日内与您联系。如有疑问请回复此邮件。",
                   chunk_index=0, embedding=zero_emb, token_count=35))
    await db.flush()

    # Sensitive words
    for word in SENSITIVE_WORDS_BUILTIN:
        db.add(SensitiveWord(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            word=word,
            category="legal" if any(w in word for w in ["诉讼", "律师", "lawsuit", "legal", "litigation"]) else "financial",
            is_active=True,
            created_at=datetime.now(timezone.utc),
        ))

    # Strategies
    for email_type, positioning, strategy, tone in DEFAULT_STRATEGIES:
        db.add(EmailTypeStrategy(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email_type=email_type,
            positioning=positioning,
            send_strategy=strategy,
            tone=tone,
            is_active=True,
        ))

    # Sample inbound email for demo
    thread_id = uuid.uuid4()
    from app.db.models import EmailThread
    thread = EmailThread(
        id=thread_id, tenant_id=tenant.id,
        account_id=sales_account.id,
        subject="产品咨询",
        status="open",
    )
    db.add(thread)
    await db.flush()

    sample_email = Email(
        id=uuid.uuid4(), tenant_id=tenant.id,
        account_id=sales_account.id,
        thread_id=thread_id,
        message_id=f"<seed-demo-{uuid.uuid4()}@example.com>",
        direction="inbound",
        from_addr="customer@example.com",
        from_name="张三",
        to_addrs=["sales@demo.emailai.local"],
        cc_addrs=[],
        subject="产品咨询",
        body_text="你好，我想了解一下贵公司的产品有哪些规格，以及交货期大概是多久？谢谢！",
        received_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db.add(sample_email)
    await db.flush()

    db.add(EmailClassification(
        id=uuid.uuid4(), email_id=sample_email.id, tenant_id=tenant.id,
        email_type="customer_inquiry", language="zh", urgency=1,
        has_sensitive=False, sensitive_words=[], confidence=0.95,
        llm_model="seed", prompt_tokens=0, completion_tokens=0,
        classified_at=datetime.now(timezone.utc),
    ))

    await db.commit()
    print(f"""
✅ Seed complete!

Tenant:   Demo Company ({DEMO_TENANT_DOMAIN})
Admin:    admin@demo.emailai.local / Admin@123456
API docs: http://localhost:8000/docs

Note: Email accounts are inactive (demo mode).
Configure real IMAP/SMTP credentials via the admin UI to enable polling.
""")


async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with SessionLocal() as db:
        await seed(db)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
