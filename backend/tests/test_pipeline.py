import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.pipeline.classifier import classify_email
from app.services.pipeline.router import decide_strategy
from app.services.pipeline.rag import retrieve_context
from app.services.llm.base import LLMMessage, LLMResponse, EmbeddingResponse


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.chat = AsyncMock(return_value=LLMResponse(
        content='{"email_type": "customer_inquiry", "language": "en", "urgency": 1, "confidence": 0.9}',
        model="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=50,
    ))
    return llm


@pytest.mark.asyncio
async def test_classify_customer_inquiry(mock_llm):
    result = await classify_email(
        llm=mock_llm,
        subject="Question about your product",
        body="I'd like to know more about pricing",
        from_addr="customer@example.com",
    )
    assert result["email_type"] == "customer_inquiry"
    assert result["language"] == "en"
    assert result["urgency"] == 1


@pytest.mark.asyncio
async def test_classify_falls_back_on_bad_json():
    llm = MagicMock()
    llm.chat = AsyncMock(return_value=LLMResponse(
        content="not valid json at all",
        model="gpt-4o-mini",
        prompt_tokens=10,
        completion_tokens=5,
    ))
    result = await classify_email(llm=llm, subject="x", body="y", from_addr="a@b.com")
    assert result["email_type"] == "other"
    assert result["confidence"] == 0.5


@pytest.mark.asyncio
async def test_classify_invalid_type_defaults_to_other():
    llm = MagicMock()
    llm.chat = AsyncMock(return_value=LLMResponse(
        content='{"email_type": "unknown_type", "language": "en", "urgency": 1, "confidence": 0.5}',
        model="test",
        prompt_tokens=10,
        completion_tokens=5,
    ))
    result = await classify_email(llm=llm, subject="x", body="y", from_addr="a@b.com")
    assert result["email_type"] == "other"


class TestDecideStrategy:
    def test_sensitive_always_human(self):
        assert decide_strategy("customer_inquiry", True, True, "auto_send") == "human_only"

    def test_spam_always_skip(self):
        assert decide_strategy("spam", False, False, None) == "skip"

    def test_ad_always_skip(self):
        assert decide_strategy("ad_no_reply", False, True, "auto_send") == "skip"

    def test_legal_always_human(self):
        assert decide_strategy("legal", False, True, "auto_send") == "human_only"

    def test_payment_always_human(self):
        assert decide_strategy("payment_reminder", False, True, "auto_send") == "human_only"

    def test_no_rag_forces_human(self):
        assert decide_strategy("customer_inquiry", False, False, "auto_send") == "human_only"

    def test_tenant_strategy_respected(self):
        assert decide_strategy("customer_inquiry", False, True, "draft_review") == "draft_review"

    def test_default_auto_send(self):
        assert decide_strategy("customer_inquiry", False, True, None) == "auto_send"

    def test_default_draft_review(self):
        assert decide_strategy("quote_request", False, True, None) == "draft_review"
