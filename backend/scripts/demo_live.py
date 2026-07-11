"""
Live end-to-end pipeline demo against the real DeepSeek API.

Runs the SAME production functions the worker uses — sensitive-word gate,
LLM classification, RAG retrieval (local lexical embedding), route decision,
and reply generation — over a handful of realistic inbound emails, printing
each stage. No database required.

Usage (inside the app image, backend/ mounted at /app):
    DEEPSEEK_KEY=sk-... python scripts/demo_live.py
"""
import asyncio
import os
import sys

from app.services.llm.openai_provider import DeepSeekProvider
from app.services.llm.local_embed import LocalHashEmbedProvider
from app.services.pipeline.classifier import classify_email
from app.services.pipeline.reply_generator import generate_reply
from app.services.pipeline.router import NO_REPLY_TYPES, decide_strategy
from app.services.pipeline.sensitive import check_sensitive_words

# ── Demo tenant config ──────────────────────────────────────────────────────
SENSITIVE_WORDS = ["律师", "诉讼", "赔偿", "投诉", "起诉"]

KB = [
    {"content": "我们的标准产品价格为每件100元。批量采购500件以上享8折，1000件以上享7折优惠。"},
    {"content": "所有订单在付款后2个工作日内发货，默认使用顺丰快递，偏远地区3-5天送达。"},
    {"content": "支持7天无理由退货，产品需保持完好未使用。质量问题15天内包退换，运费由我方承担。"},
    {"content": "产品图册、规格书和报价单可作为邮件附件发送。如需纸质版样册可申请邮寄。"},
]

EMAILS = [
    {
        "from_addr": "zhang@acme-corp.com", "from_name": "张先生",
        "subject": "批量采购价格咨询",
        "body": "你好，我们公司想批量采购你们的产品，预计1000件左右，请问价格怎么算？有没有折扣？期待回复。",
    },
    {
        "from_addr": "customer@gmail.com", "from_name": "李女士",
        "subject": "产品质量问题",
        "body": "我上周收到的产品有破损，包装也不完整，非常失望。请问怎么处理退换货？",
    },
    {
        "from_addr": "angry@client.com", "from_name": "王总",
        "subject": "严重警告",
        "body": "如果这批货的问题再不解决，我将委托律师提起诉讼，并要求全额赔偿！",
    },
    {
        "from_addr": "buyer@overseas.com", "from_name": "John Smith",
        "subject": "Product catalog request",
        "body": "Hello, could you please send me your product catalog and latest pricing? We are evaluating suppliers. Thanks.",
    },
    {
        "from_addr": "promo@spam-ads.net", "from_name": None,
        "subject": "🎉 恭喜您中奖100万",
        "body": "您已被抽中为幸运用户！点击链接立即领取100万现金大奖，手慢无！",
    },
]

TYPE_CN = {
    "customer_inquiry": "客户咨询", "quote_request": "报价请求", "material_request": "资料索取",
    "complaint": "投诉", "payment_reminder": "催付款", "order_confirm": "订单确认",
    "supplier": "供应商", "resume": "简历", "partnership": "合作邀约", "legal": "法律函件",
    "spam": "垃圾邮件", "ad_no_reply": "广告勿回", "other": "其他",
}
DECISION_CN = {
    "auto_send": "✅ 自动发送", "draft_review": "📝 草稿待审", "human_only": "👤 转人工", "skip": "⏭️  跳过",
}


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


async def retrieve(embed, email_type, query, top_k=2):
    if email_type in NO_REPLY_TYPES:
        return []
    kb_vecs = (await embed.embed([k["content"] for k in KB])).embeddings
    q_vec = (await embed.embed([query])).embeddings[0]
    scored = sorted(
        ({"content": KB[i]["content"], "score": dot(q_vec, kb_vecs[i])} for i in range(len(KB))),
        key=lambda x: x["score"], reverse=True,
    )
    floor = getattr(embed, "embed_min_score", 0.1)
    return [c for c in scored[:top_k] if c["score"] >= floor]


async def process(llm, embed, i, email):
    print("\n" + "═" * 72)
    print(f"📧 邮件 #{i}  来自 {email['from_name'] or '?'} <{email['from_addr']}>")
    print(f"   主题: {email['subject']}")
    print(f"   正文: {email['body'][:60]}...")
    print("─" * 72)

    full_text = f"{email['subject']} {email['body']}"

    # 1. Sensitive-word gate (runs before any LLM call)
    matched = check_sensitive_words(full_text, SENSITIVE_WORDS)
    if matched:
        print(f"🚨 敏感词命中: {matched}  →  强制转人工 + 生成工单 + 告警管理员")
        print(f"   {DECISION_CN['human_only']}  (未调用 LLM，直接拦截)")
        return

    # 2. Real DeepSeek classification
    cls = await classify_email(llm, email["subject"], email["body"], email["from_addr"])
    etype, lang, urg = cls["email_type"], cls.get("language", "?"), cls.get("urgency", 1)
    print(f"🧠 DeepSeek 分类: {TYPE_CN.get(etype, etype)} ({etype}) · 语言={lang} · 紧急度={urg}"
          f" · tokens={cls.get('prompt_tokens',0)}+{cls.get('completion_tokens',0)}")

    # 3. RAG retrieval (local lexical embedding)
    hits = await retrieve(embed, etype, full_text)
    if hits:
        for h in hits:
            print(f"📚 知识库命中 (score={h['score']:.3f}): {h['content'][:40]}...")
    else:
        print("📚 知识库未命中")
    rag_found = len(hits) > 0

    # 4. Route decision
    decision = decide_strategy(etype, has_sensitive=False, rag_found=rag_found, tenant_strategy=None)
    print(f"🔀 路由决策: {DECISION_CN.get(decision, decision)}")

    # 5. Reply generation (real DeepSeek), for auto_send / draft_review
    if decision in ("auto_send", "draft_review"):
        reply, model = await generate_reply(
            llm, email["subject"], email["body"], email["from_addr"],
            language=lang, tone="business", context_chunks=hits,
        )
        print(f"\n✍️  DeepSeek 生成回复 ({model}):")
        print("   " + reply.replace("\n", "\n   "))
    elif decision == "human_only":
        print("   → 无知识库依据或策略要求，转人工队列")
    elif decision == "skip":
        print("   → 垃圾/广告邮件，自动忽略不回复")


async def main():
    key = os.environ.get("DEEPSEEK_KEY")
    if not key:
        print("ERROR: set DEEPSEEK_KEY env var", file=sys.stderr)
        sys.exit(1)

    llm = DeepSeekProvider(api_key=key)
    embed = LocalHashEmbedProvider()

    print("\n🚀 企业邮件 AI · 真实链路演示 (DeepSeek + 本地向量检索)")
    print(f"   知识库: {len(KB)} 条 · 敏感词: {len(SENSITIVE_WORDS)} 个 · 测试邮件: {len(EMAILS)} 封")

    for i, email in enumerate(EMAILS, 1):
        try:
            await process(llm, embed, i, email)
        except Exception as e:
            print(f"❌ 处理失败: {type(e).__name__}: {e}")

    print("\n" + "═" * 72)
    print("✅ 演示完成 — 分类与回复均由真实 DeepSeek 生成，检索用本地向量近似")


if __name__ == "__main__":
    asyncio.run(main())
