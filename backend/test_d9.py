"""D9 自测脚本：跑一组用例，打印每轮的【问 / 答 / 检索轨迹】。

轨迹看什么（关键日志行）：
  route 选定 collection='前端'           ← 路由选了哪个库
  retrieve 主分类='前端' 命中 ...         ← 实际查的库 + 命中的文件
  grade 判定=irrelevant | relevant       ← 反省节点判够不够
  rewrite 改写：'A' -> 'B'              ← 改写 query（D9 主角）
  reroute 换库：'前端' -> '简历'          ← 换库重试（若合并了 reroute）

用法：backend/.venv/bin/python test_d9.py
判断标准见每个 case 的 expect 注释；跑完对照即可。
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import run_agent, ChatRequest

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s", stream=sys.stdout)
# 看我们自己节点的关键日志
for name in ["agent", "ai-knowledge-agent"]:
    logging.getLogger(name).setLevel(logging.INFO)
# 屏蔽 langchain/httpx 的网络噪音，只看业务轨迹
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("langchain_openai").setLevel(logging.WARNING)


# (问题, 期望说明)
CASES = [
    ("刘永庆会写react",        "应答对(简历库含React技能)，来源=简历PDF  ← D9 修复后必须过"),
    ("刘永庆搞前端框架吗",      "应答对(简历库含React组件库)，来源=简历PDF  ← D9 修复后必须过"),
    ("刘永庆的电话",           "回归守卫：仍答对 13462970432（不能被 D9 改坏）"),
    ("今天杭州天气",           "应如实说不知道(无外部工具，属 D10/D11，不在 D9 范围)"),
]


def main() -> None:
    for q, expect in CASES:
        print("\n" + "=" * 72)
        print(f"问：{q}")
        print(f"期望：{expect}")
        try:
            resp = run_agent(ChatRequest(query=q, history=[]))
            ans = resp.answer.strip()
        except Exception as e:  # noqa: BLE001
            ans = f"[异常] {e}"
        print(f"答：{ans}")
        print("-" * 72)


if __name__ == "__main__":
    main()
