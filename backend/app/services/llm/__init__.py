from app.core.security import decrypt_value
from app.services.llm.base import BaseLLMProvider
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.openai_provider import OpenAIProvider, DeepSeekProvider


def get_llm_provider(llm_config: dict) -> BaseLLMProvider:
    """Factory: build provider from tenant.settings['llm_config'] dict."""
    provider_name = llm_config.get("provider", "openai")
    api_key_enc = llm_config.get("api_key_enc", "")
    try:
        api_key = decrypt_value(api_key_enc) if api_key_enc else ""
    except Exception:
        api_key = api_key_enc  # plaintext fallback for dev

    if provider_name == "anthropic":
        return AnthropicProvider(api_key=api_key)
    elif provider_name == "deepseek":
        return DeepSeekProvider(api_key=api_key)
    else:
        base_url = llm_config.get("base_url")
        return OpenAIProvider(api_key=api_key, base_url=base_url)


def get_embed_provider(llm_config: dict) -> BaseLLMProvider:
    """
    Build an embedding provider.

    OpenAI (and compatible gateways) expose an embeddings endpoint, so they are
    used directly. DeepSeek and Anthropic do NOT provide embeddings — for those,
    and for explicit provider=="local", fall back to the API-free local hash
    embedder so retrieval still works. An explicit embed_config overrides all.
    """
    embed_config = llm_config.get("embed_config", llm_config)
    embed_provider = embed_config.get(
        "embed_provider", llm_config.get("provider", "openai")
    )

    if embed_provider in ("deepseek", "anthropic", "local"):
        from app.services.llm.local_embed import LocalHashEmbedProvider
        return LocalHashEmbedProvider()

    api_key_enc = embed_config.get("embed_api_key_enc", embed_config.get("api_key_enc", ""))
    try:
        api_key = decrypt_value(api_key_enc) if api_key_enc else ""
    except Exception:
        api_key = api_key_enc
    base_url = embed_config.get("embed_base_url")
    return OpenAIProvider(api_key=api_key, base_url=base_url)
