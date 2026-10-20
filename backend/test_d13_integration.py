"""D13 集成测试：20 道题跑批，统计表现。

用法（在 backend/ 目录下，用 venv 运行）：
    cd /Users/liuyongqing/Desktop/AI项目/ai-knowledge-agent/backend
    .venv/bin/python test_d13_integration.py

输出：
  - 终端打印每道题的结果摘要
  - d13_report.json 记录完整结果
  - 统计：正确率、编造率、各场景表现
"""
import json
import logging
import time
from datetime import datetime

# 降低日志级别，只看关键信息
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s | %(name)s | %(message)s",
)

from agent import run_agent, ChatRequest

# 20 道测试题
TEST_CASES = [
    # A. 知识库里有的问题（10 道）
    {"id": 1, "category": "A-库里有", "query": "Python 装饰器是什么", "collection": "Python", "expect": "有答案"},
    {"id": 2, "category": "A-库里有", "query": "Python 里怎么定义装饰器函数", "collection": "Python", "expect": "有答案"},
    {"id": 3, "category": "A-库里有", "query": "React Hooks 有哪些", "collection": "前端", "expect": "有答案"},
    {"id": 4, "category": "A-库里有", "query": "前端开发里什么是虚拟 DOM", "collection": "前端", "expect": "有答案"},
    {"id": 5, "category": "A-库里有", "query": "Python 列表和元组有什么区别", "collection": "Python", "expect": "有答案"},
    {"id": 6, "category": "A-库里有", "query": "React 组件之间怎么传递数据", "collection": "前端", "expect": "有答案"},
    {"id": 7, "category": "A-库里有", "query": "Python 的 GIL 是什么", "collection": "Python", "expect": "有答案"},
    {"id": 8, "category": "A-库里有", "query": "前端性能优化有哪些方法", "collection": "前端", "expect": "有答案"},
    {"id": 9, "category": "A-库里有", "query": "Python 里怎么实现多线程", "collection": "Python", "expect": "有答案"},
    {"id": 10, "category": "A-库里有", "query": "React 的生命周期方法有哪些", "collection": "前端", "expect": "有答案"},
    
    # B. 知识库里没有的问题（5 道）
    {"id": 11, "category": "B-库里没有", "query": "量子计算的基本原理", "collection": "Python", "expect": "不知道"},
    {"id": 12, "category": "B-库里没有", "query": "区块链是怎么工作的", "collection": "Python", "expect": "不知道"},
    {"id": 13, "category": "B-库里没有", "query": "Python 和 Go 语言性能对比", "collection": "Python", "expect": "不知道"},
    {"id": 14, "category": "B-库里没有", "query": "React Native 和 Flutter 哪个好", "collection": "前端", "expect": "不知道"},
    {"id": 15, "category": "B-库里没有", "query": "2024 年前端框架排名", "collection": "前端", "expect": "不知道"},
    
    # C. 闲聊（3 道）
    {"id": 16, "category": "C-闲聊", "query": "你好", "collection": "", "expect": "闲聊回复"},
    {"id": 17, "category": "C-闲聊", "query": "谢谢", "collection": "", "expect": "闲聊回复"},
    {"id": 18, "category": "C-闲聊", "query": "你是谁", "collection": "", "expect": "闲聊回复"},
    
    # D. 工具问题（2 道）
    {"id": 19, "category": "D-工具", "query": "123 乘以 456 等于多少", "collection": "", "expect": "工具回答"},
    {"id": 20, "category": "D-工具", "query": "现在几点了", "collection": "", "expect": "工具回答"},
]

def run_test():
    results = []
    stats = {
        "total": len(TEST_CASES),
        "A-库里有": {"total": 0, "pass": 0, "fail": 0},
        "B-库里没有": {"total": 0, "pass": 0, "fail": 0},
        "C-闲聊": {"total": 0, "pass": 0, "fail": 0},
        "D-工具": {"total": 0, "pass": 0, "fail": 0},
    }
    
    print("="*80)
    print(f"D13 集成测试开始 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    for tc in TEST_CASES:
        cat = tc["category"]
        stats[cat]["total"] += 1
        
        print(f"\n[{tc['id']:2d}/20] {cat} | {tc['query']}")
        
        start = time.time()
        try:
            req = ChatRequest(query=tc["query"], collection=tc["collection"])
            resp = run_agent(req)
            elapsed = time.time() - start
            
            answer = resp.answer
            answer_short = answer[:80].replace("\n", " ")
            
            # 简单判定是否通过
            passed = False
            fail_reason = ""
            
            if cat == "A-库里有":
                # 期望：有实质性回答，不是"不知道"
                if "不知道" in answer or "暂无" in answer or len(answer) < 20:
                    passed = False
                    fail_reason = "回答太短或说不知道"
                else:
                    passed = True
            
            elif cat == "B-库里没有":
                # 期望：诚实说不知道，不编造
                if "不知道" in answer or "暂无" in answer or "不太确定" in answer or "未提供" in answer:
                    passed = True
                elif len(answer) > 200:
                    # 回答太长，可能在编造
                    passed = False
                    fail_reason = "回答过长，可能编造"
                else:
                    passed = False
                    fail_reason = "没有诚实拒答"
            
            elif cat == "C-闲聊":
                # 期望：有回复，不是错误
                if len(answer) > 5 and "抱歉" not in answer and "出错" not in answer:
                    passed = True
                else:
                    passed = False
                    fail_reason = "闲聊回复异常"
            
            elif cat == "D-工具":
                # 期望：工具被调用，有具体结果
                if tc["id"] == 19:  # 计算题
                    if "56088" in answer:
                        passed = True
                    else:
                        passed = False
                        fail_reason = "计算结果不对"
                elif tc["id"] == 20:  # 时间题
                    if len(answer) > 10 and ("202" in answer or ":" in answer or "点" in answer):
                        passed = True
                    else:
                        passed = False
                        fail_reason = "时间回答异常"
            
            status = "✅" if passed else "❌"
            stats[cat]["pass" if passed else "fail"] += 1
            
            print(f"  {status} {elapsed:.1f}s | {answer_short}...")
            if fail_reason:
                print(f"  ⚠️  {fail_reason}")
            
            results.append({
                "id": tc["id"],
                "category": cat,
                "query": tc["query"],
                "expect": tc["expect"],
                "passed": passed,
                "fail_reason": fail_reason,
                "answer": answer,
                "elapsed": elapsed,
            })
            
        except Exception as e:
            elapsed = time.time() - start
            print(f"  ❌ {elapsed:.1f}s | 异常：{e}")
            stats[cat]["fail"] += 1
            results.append({
                "id": tc["id"],
                "category": cat,
                "query": tc["query"],
                "expect": tc["expect"],
                "passed": False,
                "fail_reason": f"异常：{e}",
                "answer": "",
                "elapsed": elapsed,
            })
    
    # 打印统计
    print("\n" + "="*80)
    print("测试统计")
    print("="*80)
    
    total_pass = sum(s["pass"] for s in stats.values() if isinstance(s, dict))
    total_fail = sum(s["fail"] for s in stats.values() if isinstance(s, dict))
    
    for cat, s in stats.items():
        if isinstance(s, dict) and "total" in s:
            rate = s["pass"] / s["total"] * 100 if s["total"] > 0 else 0
            print(f"{cat:12s}: {s['pass']:2d}/{s['total']:2d} 通过 ({rate:.0f}%)")
    
    print(f"\n总计: {total_pass}/{stats['total']} 通过 ({total_pass/stats['total']*100:.0f}%)")
    print(f"失败: {total_fail}/{stats['total']} ({total_fail/stats['total']*100:.0f}%)")
    
    # D13 完成标准检查
    print("\n" + "="*80)
    print("D13 完成标准检查")
    print("="*80)
    
    if total_fail <= 3:
        print("✅ 明显错误 ≤3：通过")
    else:
        print(f"❌ 明显错误 ≤3：失败（实际 {total_fail} 个）")
    
    # 检查 B 类是否有编造
    b_fabricate = [r for r in results if r["category"] == "B-库里没有" and r["fail_reason"] == "回答过长，可能编造"]
    if not b_fabricate:
        print("✅ 没有编造答案：通过")
    else:
        print(f"❌ 没有编造答案：失败（{len(b_fabricate)} 道题可能编造）")
    
    # 保存报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "stats": stats,
        "results": results,
    }
    
    report_file = "d13_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n完整报告已保存到：{report_file}")
    
    # 列出失败的题目
    failed = [r for r in results if not r["passed"]]
    if failed:
        print("\n" + "="*80)
        print(f"失败的 {len(failed)} 道题（需要修复）")
        print("="*80)
        for r in failed:
            print(f"[{r['id']:2d}] {r['category']} | {r['query']}")
            print(f"    原因：{r['fail_reason']}")
            print(f"    回答：{r['answer'][:100]}...")
            print()

if __name__ == "__main__":
    run_test()
