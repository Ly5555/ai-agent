"""D1 验证脚本：调通 GLM embedding-3 接口，拿到向量。

运行方式：cd backend && .venv/bin/python scripts/check_embedding.py
验收：维度 2048，且向量绝对值之和 > 0（防零向量 bug）。
"""
import sys
from pathlib import Path

# 把 backend/ 加入模块搜索路径，这样在任意目录运行都能 import app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_openai import OpenAIEmbeddings

from app.config import settings

# 智谱是 OpenAI 兼容网关：复用 config.py 里现成的 Key 和 base_url，只换模型名
# check_embedding_ctx_length=False 是对接非 OpenAI 官方网关的标准做法
embeddings = OpenAIEmbeddings(
    model="embedding-3",
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
    check_embedding_ctx_length=False,
)

# 拿一句话的向量
vector = embeddings.embed_query("华东仓退货流程")

print(f"向量维度: {len(vector)}（期望 2048）")
print(f"向量绝对值之和: {sum(abs(x) for x in vector):.4f}（应 > 0，防零向量 bug）")
print(f"前 5 维: {vector[:5]}")
