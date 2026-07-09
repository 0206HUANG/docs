"""
Route decision: given email_type and the tenant strategy config,
decide auto_send / draft_review / human_only.

Default fallback strategies (used when no tenant config exists):
- legal, payment_reminder, complaint (with sensitive) → human_only
- quote_request, partnership, complaint → draft_review
- customer_inquiry, material_request, order_confirm, supplier → auto_send
- spam, ad_no_reply → skip (no reply)
- resume → draft_review
"""

DEFAULT_STRATEGIES: dict[str, str] = {
    "customer_inquiry": "auto_send",
    "quote_request": "draft_review",
    "material_request": "auto_send",
    "complaint": "draft_review",
    "payment_reminder": "human_only",
    "order_confirm": "auto_send",
    "supplier": "draft_review",
    "resume": "draft_review",
    "partnership": "draft_review",
    "legal": "human_only",
    "spam": "skip",
    "ad_no_reply": "skip",
    "other": "draft_review",
}

HUMAN_ONLY_TYPES = {"legal", "payment_reminder"}
NO_REPLY_TYPES = {"spam", "ad_no_reply"}


def decide_strategy(
    email_type: str,
    has_sensitive: bool,
    rag_found: bool,
    tenant_strategy: str | None,
) -> str:
    """
    Return one of: auto_send / draft_review / human_only / skip

    Priority order:
    1. has_sensitive → always human_only
    2. email_type in NO_REPLY_TYPES → skip
    3. email_type in HUMAN_ONLY_TYPES → human_only
    4. rag_found=False → human_only (cannot compose grounded reply)
    5. tenant_strategy (from DB) if set
    6. DEFAULT_STRATEGIES fallback
    """
    if has_sensitive:
        return "human_only"
    if email_type in NO_REPLY_TYPES:
        return "skip"
    if email_type in HUMAN_ONLY_TYPES:
        return "human_only"
    if not rag_found:
        return "human_only"
    return tenant_strategy or DEFAULT_STRATEGIES.get(email_type, "draft_review")
