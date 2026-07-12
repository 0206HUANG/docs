from app.core.security import decrypt_value
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.base import BaseLLMProvider
from app.services.llm.openai_provider import DeepSeekProvider, OpenAIProvider

# OpenAI-compatible providers → (base_url, default_model).
# Most Chinese LLM vendors expose an OpenAI-compatible endpoint, so a single
# OpenAIProvider pointed at the right base_url covers them all.
# base_url + default_model verified against each vendor's official OpenAI-compatible
# docs (2026-07). Model versions drift — users can override in settings.
OPENAI_COMPATIBLE_PROVIDERS: dict[str, tuple[str, str]] = {
    "openai":    ("",                                                    "gpt-4o-mini"),
    "deepseek":  ("https://api.deepseek.com/v1",                         "deepseek-chat"),               # 深度求索(deepseek-chat 2026-07-24 EOL→可改 deepseek-v4-flash)
    "doubao":    ("https://ark.cn-beijing.volces.com/api/v3",            "doubao-1-5-pro-32k-250115"),   # 字节·豆包(火山方舟);model 需带日期后缀或用接入点 ep-xxx
    "qwen":      ("https://dashscope.aliyuncs.com/compatible-mode/v1",   "qwen-plus"),                   # 阿里·通义千问
    "glm":       ("https://open.bigmodel.cn/api/paas/v4/",               "glm-4.5-flash"),               # 智谱·GLM
    "kimi":      ("https://api.moonshot.cn/v1",                          "moonshot-v1-8k"),              # 月之暗面·Kimi
    "minimax":   ("https://api.minimaxi.com/v1",                         "MiniMax-M3"),                  # MiniMax(国内区,key 需同区)
    "hunyuan":   ("https://api.hunyuan.cloud.tencent.com/v1",            "hunyuan-turbos-latest"),       # 腾讯·混元
    "baichuan":  ("https://api.baichuan-ai.com/v1",                      "Baichuan4-Turbo"),             # 百川(model 区分大小写)
    "spark":     ("https://spark-api-open.xf-yun.com/v1",                "4.0Ultra"),                    # 讯飞·星火(api_key 格式 APIKey:APISecret)
    "stepfun":   ("https://api.stepfun.com/v1",                          "step-1-8k"),                   # 阶跃星辰·Step
}


def _decrypt(enc: str) -> str:
    try:
        return decrypt_value(enc) if enc else ""
    except Exception:
        return enc  # plaintext fallback for dev


def get_llm_provider(llm_config: dict) -> BaseLLMProvider:
    """Build a chat provider from tenant.settings['llm_config']."""
    provider_name = llm_config.get("provider", "openai")
    api_key = _decrypt(llm_config.get("api_key_enc", ""))

    if provider_name == "anthropic":
        return AnthropicProvider(api_key=api_key)

    if provider_name in OPENAI_COMPATIBLE_PROVIDERS:
        base_url, default_model = OPENAI_COMPATIBLE_PROVIDERS[provider_name]
        return OpenAIProvider(api_key=api_key, base_url=base_url or None, default_model=default_model)

    # unknown provider: honor an explicit base_url, else default OpenAI
    return OpenAIProvider(api_key=api_key, base_url=llm_config.get("base_url"))


def get_embed_provider(llm_config: dict) -> BaseLLMProvider:
    """
    Build an embedding provider. Only OpenAI's endpoint (or an explicit
    embed_config pointing at an OpenAI-compatible embedding API) is used for
    real semantic vectors; every other chat provider — DeepSeek, Anthropic and
    all the Chinese vendors, several of which have no embedding endpoint — falls
    back to the API-free local lexical embedder so RAG still works.
    """
    embed_config = llm_config.get("embed_config", llm_config)
    embed_provider = embed_config.get("embed_provider", llm_config.get("provider", "openai"))

    if embed_provider != "openai":
        from app.services.llm.local_embed import LocalHashEmbedProvider
        return LocalHashEmbedProvider()

    api_key = _decrypt(embed_config.get("embed_api_key_enc", embed_config.get("api_key_enc", "")))
    base_url = embed_config.get("embed_base_url")
    return OpenAIProvider(api_key=api_key, base_url=base_url)
