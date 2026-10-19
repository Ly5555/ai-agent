"""D11 基础三件套工具：calculator / current_time / web_search。

约定：每个工具输入字符串、返回字符串；**出错也返回字符串、不抛异常**，
方便上层「干活后反省」用「结果为空 / 含错误」来判断是否重试或换工具。
"""
from datetime import datetime


def current_time() -> str:
    """获取当前本地日期时间。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calculator(expression: str) -> str:
    """安全求值数学表达式，如 '123*456'。

    只放行数字与四则/括号；拒绝幂运算（会算出天文数字把进程卡死）与超长表达式；
    eval 时清空 builtins 做双保险。
    """
    expr = (expression or "").strip()
    if not expr:
        return "表达式为空。"
    allowed = set("0123456789+-*/(). ")
    if any(c not in allowed for c in expr):
        return "表达式包含非法字符。"
    if "**" in expr:
        return "暂不支持幂运算。"
    if len(expr) > 100:
        return "表达式过长。"
    try:
        result = eval(expr, {"__builtins__": {}}, {})  # noqa: S307 - 已白名单+禁幂+限长
        return str(result)
    except Exception as e:  # noqa: BLE001
        return f"计算错误: {e}"


def web_search(query: str) -> str:
    """联网搜索（DuckDuckGo，免费无 key），返回 top 结果的标题+摘要+链接。

    失败/无结果返回字符串（不抛异常），留给上层反省校验。
    """
    query = (query or "").strip()
    if not query:
        return "搜索词为空。"
    try:
        from duckduckgo_search import DDGS

        results = DDGS().text(query, max_results=5) or []
        if not results:
            return "未搜索到相关结果。"
        lines = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            lines.append(f"- {title}: {body}（{href}）")
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return f"搜索失败: {e}"


TOOLS = {
    "calculator": (calculator, "数学计算，入参=表达式，如 123*456"),
    "current_time": (current_time, "获取当前时间，无入参"),
    "web_search": (web_search, "联网搜索实时信息，入参=搜索词"),
}
