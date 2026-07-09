from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    role: str  # system / user / assistant
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class EmbeddingResponse:
    embeddings: list[list[float]]
    model: str
    total_tokens: int = 0


class BaseLLMProvider(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: str | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> EmbeddingResponse: ...
