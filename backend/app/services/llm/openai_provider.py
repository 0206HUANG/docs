from openai import AsyncOpenAI

from app.services.llm.base import BaseLLMProvider, EmbeddingResponse, LLMMessage, LLMResponse


class OpenAIProvider(BaseLLMProvider):
    DEFAULT_MODEL = "gpt-4o-mini"
    DEFAULT_EMBED_MODEL = "text-embedding-3-small"

    def __init__(self, api_key: str, base_url: str | None = None):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: str | None = None,
    ) -> LLMResponse:
        kwargs = {}
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        resp = await self._client.chat.completions.create(
            model=model or self.DEFAULT_MODEL,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        choice = resp.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=resp.model,
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
        )

    async def embed(self, texts: list[str], model: str | None = None) -> EmbeddingResponse:
        resp = await self._client.embeddings.create(
            input=texts,
            model=model or self.DEFAULT_EMBED_MODEL,
        )
        return EmbeddingResponse(
            embeddings=[d.embedding for d in resp.data],
            model=resp.model,
            total_tokens=resp.usage.total_tokens if resp.usage else 0,
        )


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek uses OpenAI-compatible API."""

    DEFAULT_MODEL = "deepseek-chat"

    def __init__(self, api_key: str):
        super().__init__(api_key=api_key, base_url="https://api.deepseek.com/v1")
