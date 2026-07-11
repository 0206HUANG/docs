import logging

from app.services.llm.base import BaseLLMProvider, LLMMessage

logger = logging.getLogger(__name__)

TONE_INSTRUCTIONS = {
    "formal": "Use formal, professional language. Be polite and thorough.",
    "business": "Use clear business language. Be friendly but professional.",
    "concise": "Be brief and to the point. No fluff.",
}

SYSTEM_TEMPLATE = """You are a business email assistant. Write a reply to the email below.

Rules:
1. Reply in the SAME language as the sender's email ({language}).
2. Use this tone: {tone_instruction}
3. Base your reply ONLY on the provided knowledge base context below. Do NOT invent prices, dates, policies, or facts.
4. If the context does not contain enough information to answer, say you will follow up, but do NOT guess.
5. Be helpful and complete within the constraint of available information.
6. Do not mention that you are an AI.

Knowledge base context:
{context}

Prior correspondence with this sender (maintain continuity — do NOT re-ask for information already provided, do NOT contradict earlier replies):
{history}

Sender email:
From: {from_addr}
Subject: {subject}
{body}"""


async def generate_reply(
    llm: BaseLLMProvider,
    subject: str | None,
    body: str | None,
    from_addr: str,
    language: str,
    tone: str,
    context_chunks: list[dict],
    model: str | None = None,
    history: str = "",
) -> tuple[str, str]:
    """
    Generate reply text. Returns (reply_text, llm_model_used).
    """
    tone_instruction = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["business"])
    context_text = "\n---\n".join(c["content"] for c in context_chunks) if context_chunks else "(No context available)"

    system_prompt = SYSTEM_TEMPLATE.format(
        language=language,
        tone_instruction=tone_instruction,
        context=context_text,
        history=history or "(无历史往来记录)",
        from_addr=from_addr,
        subject=subject or "(no subject)",
        body=(body or "")[:2000],
    )

    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content="Please write the reply email now."),
    ]

    resp = await llm.chat(messages, model=model, temperature=0.4, max_tokens=1500)
    return resp.content.strip(), resp.model
