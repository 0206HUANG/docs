from app.core.security import decrypt_value
from app.db.models import EmailAccount
from app.services.mail.base import BaseMailProvider
from app.services.mail.imap_smtp import IMAPSMTPProvider


def get_mail_provider(account: EmailAccount) -> BaseMailProvider:
    """Build a mail provider from an EmailAccount model."""
    password = decrypt_value(account.password_enc)
    return IMAPSMTPProvider(
        imap_host=account.imap_host,
        imap_port=account.imap_port,
        imap_ssl=account.imap_ssl,
        smtp_host=account.smtp_host,
        smtp_port=account.smtp_port,
        smtp_ssl=account.smtp_ssl,
        username=account.username,
        password=password,
    )
