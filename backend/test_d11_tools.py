"""D11 自测脚本：验证工具流程是否生效。

用法（在 backend/ 目录下，用 venv 运行）：
    cd /Users/liuyongqing/Desktop/AI项目/ai-knowledge-agent/backend
    .venv/bin/python test_d11_tools.py

测试用例：
  1. 计算题（预期：走 calculator 工具）
  2. 时间问题（预期：走 current_time 工具）
  3. 知识库问题（预期：不走工具，走 RAG）
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
    print(f"\n回答：{resp.answer[:300]}...")
    print(f"模型：{resp.model}")

# 测试 1：计算题（预期：走 calculator）
test("计算题", "123 乘以 456 等于多少")

# 测试 2：时间问题（预期：走 current_time）
test("时间问题", "现在几点了")

# 测试 3：知识库问题（预期：不走工具，走 RAG）
test("知识库问题", "Python 装饰器是什么")

print("\n" + "="*60)
print("自测完成。看日志里：")
print("  - 测试 1 应该有 'tool_select 选中工具=calculator' 和 'tool_call 调用=calculator'")
print("  - 测试 2 应该有 'tool_select 选中工具=current_time'")
print("  - 测试 3 应该没有 tool_select/tool_call 字样（走 RAG）")
