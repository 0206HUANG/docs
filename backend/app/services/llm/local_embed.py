"""
Local deterministic embedding provider — no external API required.

Used as a fallback when the configured chat provider has no embedding endpoint
(e.g. DeepSeek, Anthropic) or for offline dev/demo. It hashes character
uni-grams and bi-grams into a fixed-dimension bag-of-features vector, then
L2-normalizes. Two texts that share many characters / character-pairs get a
high cosine similarity — good enough for grounding retrieval on a small KB.

For production semantic search, configure an OpenAI-compatible embed provider
(text-embedding-3-small etc.) — this fallback is lexical, not semantic.
"""
import hashlib
import math
import re

from app.services.llm.base import BaseLLMProvider, EmbeddingResponse, LLMMessage, LLMResponse

DIM = 1536
UNIGRAM_WEIGHT = 1.0
BIGRAM_WEIGHT = 2.0  # bi-grams are more discriminative → weight them higher

_CJK = re.compile(r"[一-鿿]")
_LATIN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[tuple[str, float]]:
    """Return (token, weight) features: latin words, CJK unigrams + bigrams."""
    text = text.lower()
    feats: list[tuple[str, float]] = []
    for w in _LATIN.findall(text):
        feats.append((w, UNIGRAM_WEIGHT))
    chars = _CJK.findall(text)
    for c in chars:
        feats.append((c, UNIGRAM_WEIGHT))
    for i in range(len(chars) - 1):
        feats.append((chars[i] + chars[i + 1], BIGRAM_WEIGHT))
    return feats


def _dim(token: str) -> int:
    h = hashlib.md5(token.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % DIM


class LocalHashEmbedProvider(BaseLLMProvider):
    """Deterministic, API-free lexical embedding. Cosine-comparable, L2-normalized."""

    DEFAULT_EMBED_MODEL = "local-hash-v1"
    # Lexical similarities run lower than semantic ones — use a permissive floor.
    embed_min_score = 0.10

    def __init__(self, dim: int = DIM):
        self.dim = dim

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: str | None = None,
    ) -> LLMResponse:
        raise NotImplementedError("LocalHashEmbedProvider is embedding-only")

    async def embed(self, texts: list[str], model: str | None = None) -> EmbeddingResponse:
        vectors: list[list[float]] = []
        for t in texts:
            v = [0.0] * self.dim
            for tok, w in _tokens(t):
                v[_dim(tok)] += w
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            vectors.append([x / norm for x in v])
        return EmbeddingResponse(
            embeddings=vectors,
            model=self.DEFAULT_EMBED_MODEL,
            total_tokens=sum(len(t) for t in texts),
        )
