import email as email_lib
import email.header
import email.policy
import logging
from datetime import datetime, timezone
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

import aioimaplib
import aiosmtplib

from app.services.mail.base import BaseMailProvider, OutboundEmail, RawEmail

logger = logging.getLogger(__name__)


def _decode_header(value: str | None) -> str | None:
    if not value:
        return None
    parts = email.header.decode_header(value)
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return "".join(decoded)


class IMAPSMTPProvider(BaseMailProvider):
    def __init__(
        self,
        imap_host: str,
        imap_port: int,
        imap_ssl: bool,
        smtp_host: str,
        smtp_port: int,
        smtp_ssl: bool,
        username: str,
        password: str,
    ):
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.imap_ssl = imap_ssl
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_ssl = smtp_ssl
        self.username = username
        self.password = password
        self._imap: aioimaplib.IMAP4_SSL | aioimaplib.IMAP4 | None = None

    async def connect(self) -> None:
        if self.imap_ssl:
            self._imap = aioimaplib.IMAP4_SSL(host=self.imap_host, port=self.imap_port)
        else:
            self._imap = aioimaplib.IMAP4(host=self.imap_host, port=self.imap_port)
        await self._imap.wait_hello_from_server()
        await self._imap.login(self.username, self.password)
        await self._imap.select("INBOX")

    async def disconnect(self) -> None:
        if self._imap:
            try:
                await self._imap.logout()
            except Exception:
                pass
            self._imap = None

    async def test_connection(self) -> bool:
        try:
            await self.connect()
            await self.disconnect()
            return True
        except Exception as e:
            logger.warning("IMAP connection test failed: %s", e)
            return False

    async def fetch_new(self, since: datetime | None = None) -> list[RawEmail]:
        if not self._imap:
            await self.connect()
        if since:
            date_str = since.strftime("%d-%b-%Y")
            _, data = await self._imap.search(f'SINCE "{date_str}"')
        else:
            _, data = await self._imap.search("ALL")

        if not data or not data[0]:
            return []

        msg_ids = data[0].split()
        results: list[RawEmail] = []

        for uid in msg_ids[-200:]:  # limit batch to 200 most recent
            try:
                _, msg_data = await self._imap.fetch(uid, "(RFC822)")
                raw_bytes = msg_data[1]
                msg = email_lib.message_from_bytes(raw_bytes, policy=email_lib.policy.default)
                parsed = self._parse_message(msg)
                if parsed:
                    results.append(parsed)
            except Exception as e:
                logger.warning("Failed to parse email uid=%s: %s", uid, e)

        return results

    def _parse_message(self, msg) -> RawEmail | None:
        message_id = msg.get("Message-ID", "").strip()
        if not message_id:
            return None

        from_full = _decode_header(msg.get("From", ""))
        from_addr, from_name = self._parse_addr(from_full)
        to_raw = _decode_header(msg.get("To", "")) or ""
        cc_raw = _decode_header(msg.get("CC", "")) or ""

        body_text = None
        body_html = None
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                disp = str(part.get("Content-Disposition", ""))
                if ct == "text/plain" and "attachment" not in disp:
                    body_text = part.get_content()
                elif ct == "text/html" and "attachment" not in disp:
                    body_html = part.get_content()
                elif "attachment" in disp:
                    attachments.append({
                        "filename": part.get_filename() or "attachment",
                        "content_type": ct,
                        "data": part.get_payload(decode=True) or b"",
                    })
        else:
            if msg.get_content_type() == "text/html":
                body_html = msg.get_content()
            else:
                body_text = msg.get_content()

        received_at = None
        date_str = msg.get("Date", "")
        if date_str:
            try:
                from email.utils import parsedate_to_datetime
                received_at = parsedate_to_datetime(date_str)
                if received_at.tzinfo is None:
                    received_at = received_at.replace(tzinfo=timezone.utc)
            except Exception:
                pass

        return RawEmail(
            message_id=message_id,
            in_reply_to=msg.get("In-Reply-To"),
            references=msg.get("References"),
            from_addr=from_addr,
            from_name=from_name,
            to_addrs=self._split_addrs(to_raw),
            cc_addrs=self._split_addrs(cc_raw),
            subject=_decode_header(msg.get("Subject")),
            body_text=body_text,
            body_html=body_html,
            received_at=received_at,
            attachments=attachments,
        )

    @staticmethod
    def _parse_addr(full: str | None) -> tuple[str, str | None]:
        if not full:
            return ("", None)
        if "<" in full:
            name, _, addr = full.partition("<")
            return addr.rstrip(">").strip(), name.strip().strip('"') or None
        return full.strip(), None

    @staticmethod
    def _split_addrs(raw: str) -> list[str]:
        return [a.strip() for a in raw.split(",") if a.strip()]

    async def send(self, msg: OutboundEmail) -> str:
        mime = MIMEMultipart("mixed") if msg.attachments else MIMEMultipart("alternative")
        from_field = f"{msg.from_name} <{msg.from_addr}>" if msg.from_name else msg.from_addr
        mime["From"] = from_field
        mime["To"] = ", ".join(msg.to_addrs)
        if msg.cc_addrs:
            mime["CC"] = ", ".join(msg.cc_addrs)
        mime["Subject"] = msg.subject
        if msg.in_reply_to:
            mime["In-Reply-To"] = msg.in_reply_to
        if msg.references:
            mime["References"] = msg.references

        mime.attach(MIMEText(msg.body_text, "plain", "utf-8"))
        if msg.body_html:
            mime.attach(MIMEText(msg.body_html, "html", "utf-8"))

        for att in msg.attachments:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(att["data"])
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=att["filename"])
            mime.attach(part)

        smtp = aiosmtplib.SMTP(
            hostname=self.smtp_host,
            port=self.smtp_port,
            use_tls=self.smtp_ssl,
        )
        async with smtp:
            await smtp.login(self.username, self.password)
            await smtp.send_message(mime)

        return mime.get("Message-ID", "")
