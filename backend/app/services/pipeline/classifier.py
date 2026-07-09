import json
import logging
from datetime import datetime, timezone

from app.services.llm.base import BaseLLMProvider, LLMMessage

logger = logging.getLogger(__name__)

EMAIL_TYPES = [
    "customer_inquiry", "quote_request", "material_request", "complaint",
    "payment_reminder", "order_confirm", "supplier", "resume",
    "partnership", "legal", "spam", "ad_no_reply", "other",
]

CLASSIFY_SYSTEM = """You are an email classifier for a business. Classify the given email and return ONLY valid JSON.

Output schema:
{
  "email_type": "<one of the types listed>",
  "language": "<ISO 639-1 code, e.g. zh, en, ja>",
  "urgency": <1, 2, or 3>,
  "confidence": <0.0 to 1.0>
}

Email types:
- customer_inquiry: General questions from customers
- quote_request: Asking for pricing/quote
- material_request: Requesting catalogs, samples, specs
- complaint: Complaints, disputes, bad experience
- payment_reminder: Payment related, invoices, overdue
- order_confirm: Order status, confirmation, shipping
- supplier: Supplier / vendor communications
- resume: Job applications, CVs
- partnership: Business cooperation proposals
- legal: Legal notices, contracts, regulatory
- spam: Spam, phishing attempts
- ad_no_reply: Newsletters, promotional, no reply needed
- other: Does not fit above

Urgency: 1=low, 2=medium, 3=high/urgent"""


async def classify_email(
    llm: BaseLLMProvider,
    subject: str | None,
    body: str | None,
    from_addr: str,
    model: str | None = None,
) -> dict:
    """Run LLM classification. Returns dict with email_type, language, urgency, confidence."""
    content = f"From: {from_addr}\nSubject: {subject or '(no subject)'}\n\n{(body or '')[:3000]}"
    messages = [
        LLMMessage(role="system", content=CLASSIFY_SYSTEM),
        LLMMessage(role="user", content=content),
    ]
    resp = await llm.chat(messages, model=model, temperature=0.1, response_format="json")
    try:
        data = json.loads(resp.content)
        if data.get("email_type") not in EMAIL_TYPES:
            data["email_type"] = "other"
        data.setdefault("urgency", 1)
        data.setdefault("confidence", 0.8)
        data["prompt_tokens"] = resp.prompt_tokens
        data["completion_tokens"] = resp.completion_tokens
        data["llm_model"] = resp.model
        return data
    except Exception as e:
        logger.warning("Classification JSON parse failed: %s | raw=%s", e, resp.content[:200])
        return {
            "email_type": "other",
            "language": "en",
            "urgency": 1,
            "confidence": 0.5,
            "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens,
            "llm_model": resp.model,
        }
