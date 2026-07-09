import anthropic

from app.services.llm.base import BaseLLMProvider, EmbeddingResponse, LLMMessage, LLMResponse


class AnthropicProvider(BaseLLMProvider):
    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: str | None = None,
    ) -> LLMResponse:
        system_msgs = [m for m in messages if m.role == "system"]
        other_msgs = [m for m in messages if m.role != "system"]
        system_text = system_msgs[0].content if system_msgs else anthropic.NOT_GIVEN

        resp = await self._client.messages.create(
            model=model or self.DEFAULT_MODEL,
            max_tokens=max_tokens,
            system=system_text,
            messages=[{"role": m.role, "content": m.content} for m in other_msgs],
            temperature=temperature,
        )
        return LLMResponse(
            content=resp.content[0].text,
            model=resp.model,
            prompt_tokens=resp.usage.input_tokens,
            completion_tokens=resp.usage.output_tokens,
        )

    async def embed(self, texts: list[str], model: str | None = None) -> EmbeddingResponse:
        raise NotImplementedError("Use OpenAI provider for embeddings")
