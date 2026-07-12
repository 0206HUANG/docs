from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawEmail:
    message_id: str
    in_reply_to: str | None
    references: str | None
    from_addr: str
    from_name: str | None
    to_addrs: list[str]
    cc_addrs: list[str]
    subject: str | None
    body_text: str | None
    body_html: str | None
    received_at: datetime | None
    attachments: list[dict] = field(default_factory=list)
    # each attachment: {filename, content_type, data: bytes}


@dataclass
class OutboundEmail:
    from_addr: str
    from_name: str | None
    to_addrs: list[str]
    cc_addrs: list[str]
    subject: str
    body_text: str
    body_html: str | None = None
    in_reply_to: str | None = None
    references: str | None = None
    attachments: list[dict] = field(default_factory=list)
    # each attachment: {filename, content_type, data: bytes}


class BaseMailProvider(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def fetch_new(self, since: datetime | None = None) -> list[RawEmail]: ...

    @abstractmethod
    async def send(self, msg: OutboundEmail) -> str: ...

    @abstractmethod
    async def test_connection(self) -> bool: ...

    @abstractmethod
    async def delete_message(self, message_id: str) -> bool: ...
