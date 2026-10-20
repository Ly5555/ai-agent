"""D12 自测脚本：验证 grounding 校验和知识缺口记录。

用法（在 backend/ 目录下，用 venv 运行）：
    cd /Users/liuyongqing/Desktop/AI项目/ai-knowledge-agent/backend
    .venv/bin/python test_d12_grounding.py

测试用例：
  1. 知识库里有的问题（预期：grounding 保留原答案，不记录缺口）
  2. 知识库里没有的问题（预期：grounding 降级或记录缺口）
  3. 刁钻问题（预期：grounding 标注"不太确定"并记录缺口）
"""
import logging

# 开启日志，看完整轨迹
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)

from agent import run_agent, ChatRequest

def test(label: str, query: str, collection: str = "Python"):
    print(f"\n{'='*60}")
    print(f"测试：{label}")
    print(f"问题：{query}")
    print(f"知识库：{collection}")
    print(f"{'='*60}")
    req = ChatRequest(query=query, collection=collection)
    resp = run_agent(req)
    print(f"\n回答：{resp.answer[:400]}...")
    print(f"模型：{resp.model}")

# 测试 1：知识库里有的问题（预期：grounding 保留原答案）
test(
    "知识库里有的问题",
    "Python 装饰器是什么",
    collection="Python",
)

# 测试 2：知识库里没有的问题（预期：记录知识缺口）
test(
    "知识库里没有的问题",
    "量子计算的基本原理",
    collection="Python",
)

# 测试 3：刁钻问题（预期：grounding 标注"不太确定"）
test(
    "刁钻问题（跨领域对比）",
    "Python 和 JavaScript 在内存管理上有什么区别",
    collection="Python",
)

print("\n" + "="*60)
print("自测完成。检查：")
print("  1. 日志里有没有 'grounding 校验完成'")
print("  2. 日志里有没有 'grounding 记录知识缺口'")
print("  3. data/gaps.jsonl 文件有没有新增记录")
print("\n查看 gaps.jsonl：")
print("  cat /Users/liuyongqing/Desktop/AI项目/ai-knowledge-agent/data/gaps.jsonl")
