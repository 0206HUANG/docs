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
    """Embedding always uses an OpenAI-compatible provider."""
    embed_config = llm_config.get("embed_config", llm_config)
    api_key_enc = embed_config.get("embed_api_key_enc", embed_config.get("api_key_enc", ""))
    try:
        api_key = decrypt_value(api_key_enc) if api_key_enc else ""
    except Exception:
        api_key = api_key_enc
    base_url = embed_config.get("embed_base_url")
    return OpenAIProvider(api_key=api_key, base_url=base_url)
