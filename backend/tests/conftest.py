import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.db.models import (
    Email, EmailAccount, EmailClassification, Tenant, User, Role, UserRole
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.fixture
def make_email(tenant_id):
    def _make(
        subject="Test subject",
        body="Hello, I need help",
        from_addr="customer@example.com",
        account_id=None,
    ):
        return Email(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            account_id=account_id or uuid.uuid4(),
            message_id=f"<test-{uuid.uuid4()}@example.com>",
            direction="inbound",
            from_addr=from_addr,
            from_name="Test Customer",
            to_addrs=["sales@mycompany.com"],
            cc_addrs=[],
            subject=subject,
            body_text=body,
            received_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
    return _make


@pytest.fixture
def make_account(tenant_id):
    def _make(positioning="sales"):
        return EmailAccount(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            email_address="sales@mycompany.com",
            provider="generic",
            imap_host="imap.example.com",
            imap_port=993,
            imap_ssl=True,
            smtp_host="smtp.example.com",
            smtp_port=465,
            smtp_ssl=True,
            username="sales@mycompany.com",
            password_enc="encrypted",
            positioning=positioning,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
    return _make
