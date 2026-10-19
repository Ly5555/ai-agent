"""D9 自测脚本：验证 rewrite 循环是否生效。

用法（在 backend/ 目录下，用 venv 运行）：
    cd /Users/liuyongqing/Desktop/AI项目/ai-knowledge-agent/backend
    .venv/bin/python test_d9_rewrite.py

测试用例设计：
  1. 直接命中（不触发 rewrite）：问 Python 笔记里明确有的内容
  2. 需要改写才能命中（触发 rewrite 循环）：用不同关键词问同一个知识点
  3. 库里完全没有（触发 rewrite 但重试耗尽后兜底说不知道）
"""
import logging

# 开启日志，看完整轨迹
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)

from agent import run_agent, ChatRequest

def test(label: str, query: str, collection: str = ""):
    print(f"\n{'='*60}")
    print(f"测试：{label}")
    print(f"问题：{query}")
    print(f"{'='*60}")
    req = ChatRequest(query=query, collection=collection)
    resp = run_agent(req)
    print(f"\n回答：{resp.answer[:200]}...")
    print(f"模型：{resp.model}")

# 测试 1：直接命中（预期：不触发 rewrite）
test(
    "直接命中（Python 笔记里有装饰器）",
    "Python 装饰器是什么",
    collection="Python",
)

# 测试 2：换个说法问（预期：可能触发 rewrite）
test(
    "换个说法问（用函数增强代替装饰器关键词）",
    "Python 里怎么给函数加额外功能",
    collection="Python",
)

# 测试 3：库里没有（预期：rewrite 重试后兜底说不知道）
test(
    "库里没有的问题",
    "量子计算的基本原理",
    collection="Python",
)

print("\n" + "="*60)
print("自测完成。看日志里有没有 'rewrite 改写' 字样，")
print("有的话说明 D9 的 rewrite 循环生效了。")
