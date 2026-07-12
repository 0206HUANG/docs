"""
Verify that deleting an email also removes it from Gmail (IMAP).

Picks a real inbound email that is currently in the Gmail INBOX, confirms it's
there, calls the provider's delete_message, and confirms it's gone. (Gmail
keeps a copy in All Mail, so this is recoverable — it just leaves the inbox.)

    python scripts/verify_delete.py
"""
import asyncio

import aioimaplib
from sqlalchemy import select

from app.core.security import decrypt_value
from app.db.base import AsyncSessionLocal
from app.db.models import Email, EmailAccount, Tenant
from app.services.mail import get_mail_provider

GMAIL = "yihu73385@gmail.com"
SENDER = "bosheng@graduate.utm.my"


async def gmail_inbox_count(message_id: str, pw: str) -> int:
    im = aioimaplib.IMAP4_SSL("imap.gmail.com", 993)
    await im.wait_hello_from_server()
    await im.login(GMAIL, pw)
    await im.select("INBOX")
    r = await im.search("HEADER", "Message-ID", message_id.strip("<>"))
    n = len(r.lines[0].split()) if r.lines and r.lines[0] else 0
    await im.logout()
    return n


async def main():
    async with AsyncSessionLocal() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.domain == "demo.emailai.local"))).scalar_one()
        acct = (await db.execute(
            select(EmailAccount).where(EmailAccount.tenant_id == tenant.id, EmailAccount.email_address == GMAIL)
        )).scalar_one()
        email = (await db.execute(
            select(Email).where(
                Email.tenant_id == tenant.id,
                Email.from_addr == SENDER,
                Email.is_deleted == False,
            ).order_by(Email.received_at.desc())
        )).scalars().first()
        if not email:
            print(f"未找到来自 {SENDER} 的未删邮件,先从学校邮箱发一封再试")
            return
        mid, eid, subj = email.message_id, email.id, email.subject
        pw = decrypt_value(acct.password_enc)

    print(f"目标邮件: {subj}")
    before = await gmail_inbox_count(mid, pw)
    print(f"删除前 · Gmail 收件箱匹配: {before} 封")

    provider = get_mail_provider(acct)
    removed = await provider.delete_message(mid)
    await provider.disconnect()
    print(f"delete_message 返回: {removed}")

    await asyncio.sleep(2)
    after = await gmail_inbox_count(mid, pw)
    print(f"删除后 · Gmail 收件箱匹配: {after} 封")

    async with AsyncSessionLocal() as db:
        e = (await db.execute(select(Email).where(Email.id == eid))).scalar_one()
        e.is_deleted = True
        await db.commit()

    print("\n" + "═" * 60)
    ok = before > 0 and after == 0 and removed
    print(f"{'✅' if ok else '⚠️'} Gmail 收件箱 {before} → {after} · 本地 is_deleted=True")
    print("✅ 删除已同步到 Gmail(邮件已移出收件箱,仍可在 All Mail 找回)" if ok else "⚠️ 请检查删除逻辑")


if __name__ == "__main__":
    asyncio.run(main())
