import math

from app.services.llm.local_embed import DIM, LocalHashEmbedProvider


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


async def test_embed_dim_and_l2_normalized():
    p = LocalHashEmbedProvider()
    v = (await p.embed(["产品价格咨询"])).embeddings[0]
    assert len(v) == DIM
    assert abs(math.sqrt(sum(x * x for x in v)) - 1.0) < 1e-6


async def test_related_text_scores_higher_than_unrelated():
    p = LocalHashEmbedProvider()
    vecs = (await p.embed([
        "你们的产品价格是多少钱",          # query
        "我们的标准产品价格为每件100元",    # related — shares 产品/价格
        "所有订单付款后2个工作日内发货",    # unrelated
    ])).embeddings
    related = _dot(vecs[0], vecs[1])
    unrelated = _dot(vecs[0], vecs[2])
    assert related > unrelated
    assert related >= p.embed_min_score


async def test_identical_text_cosine_is_one():
    p = LocalHashEmbedProvider()
    vecs = (await p.embed(["退换货政策", "退换货政策"])).embeddings
    assert abs(_dot(vecs[0], vecs[1]) - 1.0) < 1e-6


async def test_chat_not_supported():
    p = LocalHashEmbedProvider()
    try:
        await p.chat([])
        assert False, "expected NotImplementedError"
    except NotImplementedError:
        pass
