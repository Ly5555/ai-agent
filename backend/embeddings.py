"""Embedding 工厂 + 批量向量化 + D1 自检脚本。

智谱 GLM embedding-3 是 OpenAI 兼容网关，复用 config 里的 Key/base_url。

运行（在 backend/ 下）：
    .venv/bin/python embeddings.py
验收：维度 2048，且向量绝对值之和 > 0（防零向量 bug）。
"""
from langchain_openai import OpenAIEmbeddings

from config import settings

EMBED_BATCH = 32  # 向量化接口单次提交的块数上限


def make_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        check_embedding_ctx_length=False,
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化，按 EMBED_BATCH 分桶提交，避免单次超限。"""
    if not texts:
        return []
    emb = make_embeddings()
    return [
        v
        for i in range(0, len(texts), EMBED_BATCH)
        for v in emb.embed_documents(texts[i : i + EMBED_BATCH])
    ]


if __name__ == "__main__":
    # D1 验证：调通 GLM embedding-3，拿到一句向量的维度与非零校验
    vector = make_embeddings().embed_query("华东仓退货流程")
    print(f"向量维度: {len(vector)}（期望 2048）")
    print(f"向量绝对值之和: {sum(abs(x) for x in vector):.4f}（应 > 0，防零向量 bug）")
    print(f"前 5 维: {vector[:5]}")
