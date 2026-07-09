import logging
import uuid

from app.repos.kb_repo import KBChunkRepo, KBGroupRepo
from app.services.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

SKIP_TYPES = {"spam", "ad_no_reply"}


async def retrieve_context(
    embed_provider: BaseLLMProvider,
    kb_group_repo: KBGroupRepo,
    kb_chunk_repo: KBChunkRepo,
    positioning: str,
    email_type: str,
    query_text: str,
    top_k: int = 5,
) -> tuple[list[dict], list[uuid.UUID]]:
    """
    Retrieve relevant knowledge base chunks for the email.
    Returns (chunks_list, chunk_ids) where chunks_list contains {content, score}.
    Returns empty if email type should not be retrieved (spam/ad).
    """
    if email_type in SKIP_TYPES:
        return [], []

    groups = await kb_group_repo.find_for_email(positioning=positioning, email_type=email_type)
    if not groups:
        logger.info("No KB groups matched positioning=%s type=%s", positioning, email_type)
        return [], []

    group_ids = [g.id for g in groups]

    try:
        embed_resp = await embed_provider.embed([query_text])
        embedding = embed_resp.embeddings[0]
    except Exception as e:
        logger.error("Embedding failed: %s", e)
        return [], []

    chunks = await kb_chunk_repo.similarity_search(
        embedding=embedding,
        group_ids=group_ids,
        top_k=top_k,
        min_score=0.65,
    )

    result = [{"content": c.content, "score": score, "id": str(c.id)} for c, score in chunks]
    chunk_ids = [c.id for c, _ in chunks]
    return result, chunk_ids
