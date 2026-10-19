"""D10 自测脚本：验证 router 意图分流是否生效。

用法（在 backend/ 目录下，用 venv 运行）：
    cd /Users/liuyongqing/Desktop/AI项目/ai-knowledge-agent/backend
    .venv/bin/python test_d10_router.py

测试用例：
  1. 闲聊（预期：router 判 chat → chat_generate，不触发 retrieve）
  2. 知识库问题（预期：router 判 knowledge → route → retrieve）
  3. 工具问题（预期：router 判 tool → tool_placeholder）
"""
import logging

# 开启日志，看完整轨迹
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)

from agent import run_agent, ChatRequest

def test(label: str, query: str):
    print(f"\n{'='*60}")
    print(f"测试：{label}")
    print(f"问题：{query}")
    print(f"{'='*60}")
    req = ChatRequest(query=query)
    resp = run_agent(req)
    print(f"\n回答：{resp.answer[:200]}...")
    print(f"模型：{resp.model}")

# 测试 1：闲聊（预期：不触发 retrieve）
test("闲聊问候", "你好")

# 测试 2：知识库问题（预期：触发 retrieve）
test("知识库问题", "Python 装饰器是什么")

# 测试 3：工具问题（预期：走 tool_placeholder）
test("工具问题", "今天天气怎么样")

print("\n" + "="*60)
print("自测完成。看日志里：")
print("  - 测试 1 应该没有 'retrieve' 字样（走 chat_generate）")
print("  - 测试 2 应该有 'retrieve' 字样（走知识库 RAG）")
print("  - 测试 3 应该有 'tool_placeholder' 字样（走工具占位）")
