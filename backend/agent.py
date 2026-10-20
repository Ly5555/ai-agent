"""个人知识库 Agent：LangGraph 对话图 + 对外 run_agent() + 请求/响应模型。

扁平化后所有 backend 模块都在同一层，互相直接 import（from config / from vector_store ...）。

当前版本（D12）：
  router(LLM 意图分类) → {
    knowledge → route(选库) → retrieve → grade → { 相关: generate | 不相关: rewrite 循环 } → grounding（回答前反省）
    chat → chat_generate（闲聊直答）
    tool → tool_select → tool_call → tool_reflect（干活后反省）→ generate → grounding（回答前反省）
  }

D12 核心：回答前 Grounding 逐句校验 + 知识缺口记录。
D11 核心：基础三件套工具（calculator / current_time / web_search）+ 干活后反省。
D10 核心：router 入口分流——闲聊不触发检索，工具问题走工具流程，知识库问题才走 RAG。
D9 核心：rewrite 节点实现「检索后反省 / Self-RAG」——召回不够就改写 query 重查。

TODO（面试进阶，自己补）：
  - D13：集成测试日
"""
from datetime import datetime
import json
import logging

from typing import Literal, TypedDict

from pydantic import BaseModel

from config import make_http_client, settings

from vector_store import get_collection, query as vs_query

logger = logging.getLogger(__name__)
from langchain_openai import ChatOpenAI

from tool import TOOLS

# ---------- 请求 / 响应模型 ----------
class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    query: str
    history: list[Message] = []
    collection: str = ""  # 可选：前端手动指定知识库，留空则由 route 自动路由


class ChatResponse(BaseModel):
    answer: str
    model: str = "mock"


# ---------- 智能体图 ----------
class ChatState(TypedDict):
    query: str
    history: list[dict]
    answer: str
    context: list  # RAG 检索结果
    collection: str  # 路由节点写入，retrieve 读取
    grade: str
    retry_count: int = 0
    tried: list = []  # D9：已检索过的知识库，reroute 时避免重复
    intent: str  # D10：router 写入意图分类
    tool_name: str = ""  # D11：tool_select 写入选中的工具名
    tool_input: str = ""  # D11：tool_select 写入工具入参
    tool_result: str = ""  # D11：tool_call 写入工具返回结果
    tool_name: str
    tool_input: str
    tool_result: str

def retrieve(state: ChatState) -> dict:
    # RAG 召回：向量库查询（强制按 collection 过滤），结果存入 state.context
    # collection 必须由前端下拉框显式传入（Step 4），后端不私自默认；
    # 未传 collection 则不检索，交给 generate 如实说"不在知识库里"
    collection = state.get("collection")
    if collection:
        hits = vs_query(state["query"], collection, top_k=4)
        logger.info("retrieve 主分类=%r 命中 %d 块：%s", collection, len(hits), [h.get("source") for h in hits])
        if hits:
            return {"context": _to_ctx(hits)}
    # 路由没选到库（或未召回到）→ 退化搜全部分类取 top 结果，
    # 避免一次路由失误就直接"不知道"（D6 修复日健壮性补强）
    logger.warning("retrieve 主分类未命中，退化搜全部分类：collection=%r", collection)
    try:
        valid = sorted({
            m["collection"]
            for m in get_collection().get(include=["metadatas"])["metadatas"]
            if m.get("collection")
        })
    except Exception:  # noqa: BLE001
        valid = []
    merged = []
    for c in valid:
        try:
            merged.extend(vs_query(state["query"], c, top_k=2))
        except Exception:  # noqa: BLE001
            continue
    merged.sort(key=lambda h: h.get("score", 0), reverse=True)
    logger.warning("retrieve 兜底召回 %d 块：%s", len(merged), [(h.get("source"), h.get("page")) for h in merged[:4]])
    return {"context": _to_ctx(merged[:4])}


def _to_ctx(hits):
    # D6·①：保留整条 hit（含 source/page），供 generate 注入引用来源
    return [
        {"text": h["text"], "source": h["source"], "page": h["page"]}
        for h in hits
    ]

def tool_select(state: ChatState) -> dict:
    """D11 工具选择节点：用 LLM 判断是否需要工具，需要则选工具并提取入参。
    返回格式：{"tool_name": "calculator", "tool_input": "123*456"} 或 {"tool_name": "none", "tool_input": ""}
    """
    if not settings.llm_api_key:
        logger.warning("tool_select 无密钥，跳过工具选择")
        return {"tool_name": "none", "tool_input": ""}
    
    tool_list = "\n".join(f"- {name}: {desc}" for name, (fn, desc) in TOOLS.items())
    prompt = (
        "你有这些工具：\n" + tool_list + "\n\n"
        "判断用户问题是否需要工具。需要就只回 `工具名|入参`，不需要就回 `none`。\n\n"
        "示例：\n"
        "- '123乘以456' → calculator|123*456\n"
        "- '现在几点了' → current_time|\n"
        "- '今天天气怎么样' → web_search|今天天气\n"
        "- 'Python 装饰器是什么' → none\n\n"
        f"用户问题：{state['query']}"
    )
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
            http_client=make_http_client(),
        )
        ans = llm.invoke(prompt).content.strip()
        
        # 解析结果：工具名|入参 或 none
        if "none" in ans.lower():
            logger.info("tool_select 判定不需要工具 | query=%r", state.get("query"))
            return {"tool_name": "none", "tool_input": ""}
        
        # 尝试解析 工具名|入参
        if "|" in ans:
            parts = ans.split("|", 1)
            tool_name = parts[0].strip()
            tool_input = parts[1].strip() if len(parts) > 1 else ""
            # 验证工具名是否合法
            if tool_name in TOOLS:
                logger.info("tool_select 选中工具=%r 入参=%r | query=%r", 
                           tool_name, tool_input, state.get("query"))
                return {"tool_name": tool_name, "tool_input": tool_input}
            else:
                logger.warning("tool_select 工具名不合法=%r，降级为 none", tool_name)
                return {"tool_name": "none", "tool_input": ""}
        else:
            logger.warning("tool_select 返回格式不对=%r，降级为 none", ans)
            return {"tool_name": "none", "tool_input": ""}
    except Exception:  # noqa: BLE001
        logger.exception("tool_select 调用 LLM 失败")
        return {"tool_name": "none", "tool_input": ""}    

def tool_call(state: ChatState) -> dict:
    """D11 工具调用节点：根据 tool_name 调用对应工具，结果写入 tool_result。"""
    name = state.get("tool_name")
    tool_input = state.get("tool_input", "")
    if name and name in TOOLS:
        fn, _ = TOOLS[name]
        # current_time 不接受参数，其他工具接受一个字符串参数
        try:
            if name == "current_time":
                result = fn()
            else:
                result = fn(tool_input)
            logger.info("tool_call 调用=%r 入参=%r 结果=%r", name, tool_input, result[:100])
            return {"tool_result": result}
        except Exception as e:  # noqa: BLE001
            logger.exception("tool_call 调用工具失败")
            return {"tool_result": f"工具调用失败: {e}"}
    logger.warning("tool_call 工具不存在=%r", name)
    return {"tool_result": ""}


def tool_reflect(state: ChatState) -> dict:
    """D11 干活后反省节点：校验工具结果是否有效。
    无效则清空 tool_name（让后续 generate 知道工具失败了），有效则保留。
    """
    result = state.get("tool_result", "")
    tool_name = state.get("tool_name", "")
    
    # 校验规则：结果为空、含错误关键词、过短都视为无效
    is_invalid = (
        not result
        or "错误" in result
        or "失败" in result
        or "为空" in result
        or len(result) < 3
    )
    
    if is_invalid:
        logger.warning("tool_reflect 判定工具结果无效=%r，清空 tool_name", result[:50])
        return {"tool_name": "none", "tool_result": ""}  # 清空，让 generate 走兜底
    
    logger.info("tool_reflect 判定工具结果有效 | tool=%r", tool_name)
    return {}  # 保留原状

def grounding(state: ChatState) -> dict:
    """D12 Grounding 校验节点：逐句校验生成回答是否与 context 一致。
    目前仅做占位，后续可实现逐句对比、标注来源、纠错等功能。
    """
    answer = state.get("answer", "")
    context = state.get("context", [])
    query = state.get("query", "")
    collection = state.get("collection", "")

    if not answer or not context:
        return {"answer": answer}
    
    if not settings.llm_api_key:
        return {"answer": answer}
    ctx_text = "\n\n".join(
        f"[资料{i}] {item.get('text', '')}" for i, item in enumerate(context, 1)
    )
    prompt = (
        "你是答案校验员。下面给出了用户问题的答案和参考资料。\n"
        "请逐句检查答案中的每一句话，判断它是否有参考资料的依据。\n"
        "对于每一句，输出：\n"
        "- 有依据：直接保留原句\n"
        "- 无依据：改成「这一点我不太确定」\n\n"
        "只输出修改后的完整答案，不要任何解释。\n\n"
        f"用户问题：{query}\n\n"
        f"参考答案：\n{answer}\n\n"
        f"参考资料：\n{ctx_text}"
    )
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
            http_client=make_http_client(),
        )
        checked_answer = llm.invoke(prompt).content.strip()
        logger.info("grounding 校验完成 | query=%r", query)
        uncertainty_count = checked_answer.count("不太确定")
        # 如果答案被大幅缩短（超过50%）或很短，也视为知识缺口
        length_ratio = len(checked_answer) / max(len(answer), 1)
        is_significantly_shortened = length_ratio < 0.5 or len(checked_answer) < 50
        
        if uncertainty_count >= 1 or "暂无相关信息" in answer or is_significantly_shortened:
            _record_gap(query, collection)
            logger.info("grounding 记录知识缺口 | query=%r | 不确定数=%d | 长度比=%.2f", 
                       query, uncertainty_count, length_ratio)
        
        logger.info("grounding 校验完成 | 原答案长度=%d 校验后长度=%d", len(answer), len(checked_answer))
        return {"answer": checked_answer}
    except Exception:  # noqa: BLE001
        logger.exception("grounding 调用 LLM 失败")
        return {"answer": answer}  # 出错就返回原答案
def _record_gap(query: str, collection: str):
    """D12：把知识缺口写入 data/gaps.jsonl。"""
    try:
        import os
        # 使用绝对路径，确保从任何目录运行都能正确写入
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gaps_file = os.path.join(project_root, "data", "gaps.jsonl")
        
        gap = {
            "query": query,
            "collection": collection,
            "timestamp": datetime.now().isoformat(),
        }
        with open(gaps_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(gap, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        logger.exception("记录知识缺口失败")

def generate(state: ChatState) -> dict:
    # D11：如果有工具结果，优先用工具结果回答
    tool_result = state.get("tool_result", "")
    tool_name = state.get("tool_name", "")
    if tool_result and tool_name and tool_name != "none":
        if not settings.llm_api_key:
            return {"answer": f"[mock] 工具结果：{tool_result}"}
        try:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=0.3,
                http_client=make_http_client(),
            )
            prompt = (
                f"用户问了需要工具的问题，工具 {tool_name} 返回了以下结果：\n"
                f"{tool_result}\n\n"
                f"请根据工具结果回答用户问题：{state['query']}"
            )
            reply = llm.invoke(prompt).content
            logger.info("generate 使用工具结果回答 | tool=%r", tool_name)
            return {"answer": reply}
        except Exception:  # noqa: BLE001
            logger.exception("generate 调用 LLM 失败（工具模式）")
            return {"answer": "抱歉，生成回答时出错了，请稍后再试。"}
    
    # 有密钥就走真实 LLM，否则返回 mock，保证本地能跑通
    if settings.llm_api_key:
        try:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                temperature=0.3,
                http_client=make_http_client(),  # 直连智谱（忽略终端代理）
            )
            # D6·①：每块标注来源，并令模型末尾列引用（RAG 接通 + 来源引用）
            context = state.get("context", [])
            blocks = []
            for i, item in enumerate(context, 1):
                src = item.get("source", "未知来源")
                page = item.get("page", "")
                page_tag = f"第{page}页" if page else ""
                blocks.append(f"[资料{i}｜来源：《{src}》{page_tag}]\n{item.get('text', '')}")
            ctx = "\n\n".join(blocks)
            prompt = (
                "根据以下资料回答问题，资料中没有的信息如实说不知道。\n"
                "若资料中包含答案，回答结束后另起一段以「引用来源：」开头，列出你实际用到的资料编号及文件名与页码；"
                "若资料中完全没有相关信息，请不要输出「引用来源：」行，直接说明资料中未提供该信息即可。\n"
                f"{ctx}\n\n问题：{state['query']}"
            )
            reply = llm.invoke(prompt).content
            return {"answer": reply}
        except Exception:  # noqa: BLE001
            # D6·③：先记真实错误，再返回安全兜底（不编答案）
            logger.exception("generate 调用 LLM 失败")
            return {"answer": "抱歉，生成回答时出错了，请稍后再试。"}
    # 未配置密钥：诚实返回占位，不伪装成真实回答
    return {"answer": f"[mock] 未配置 LLM_API_KEY，返回占位回答（你问了：{state['query']}）"}

def grade(state: ChatState) -> dict:
    """grade 节点：判断召回的 context 是否足以回答问题。
    D8 仅把结果写进 state.grade，不分支（分支是 D9 的活）。"""
    if not settings.llm_api_key:
        return {"grade": "irrelevant"}  # 无密钥时保守兜底
    context = state.get("context", [])
    if not context:
        return {"grade": "irrelevant"}  # 没召回到资料，肯定不够答
    ctx_text = "\n\n".join(
        f"[资料{i}] {item.get('text', '')}" for i, item in enumerate(context, 1)
    )
    prompt = (
        "你是检索质量评委。下面给出用户问题和检索到的资料。\n"
        "判断资料是否足以回答该问题：只有资料中明确包含答案时才判 relevant，"
        "含糊、缺失关键信息或完全无关一律判 irrelevant。\n"
        "不要解释，只回复一个词：relevant 或 irrelevant。\n\n"
        f"用户问题：{state['query']}\n\n"
        f"检索到的资料：\n{ctx_text}"
    )
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
            http_client=make_http_client(),
        )
        ans = llm.invoke(prompt).content.strip().lower()
        # 注意：不能写 "relevant" in ans —— "irrelevant" 也含 "relevant" 子串会翻错
        if "irrelevant" in ans:
            grade_val = "irrelevant"
        elif "relevant" in ans:
            grade_val = "relevant"
        else:
            grade_val = "irrelevant"  # 拿不准时保守判 irrelevant
        logger.info("grade 判定=%s | query=%r", grade_val, state.get("query"))
        return {"grade": grade_val}
    except Exception:  # noqa: BLE001
        logger.exception("grade 调用 LLM 失败")
        return {"grade": "irrelevant"}


def rewrite(state: ChatState) -> dict:
    """D9 改写节点：grade 判 irrelevant 后，让 LLM 把 query 换个说法再回去重查。
    这就是「检索后反省 / Self-RAG」——召回不够就改写 query 重查。"""
    if not settings.llm_api_key:
        return {"query": state["query"], "retry_count": state.get("retry_count", 0) + 1}
    prompt = (
        "你是 query 改写专家。下面的用户问题在知识库里没检索到相关内容，"
        "请换一种表述方式重新描述这个问题。\n"
        "要求：\n"
        "- 保持原始语义不变\n"
        "- 尝试使用同义词、不同角度、或更宽泛/更具体的关键词\n"
        "- 只返回改写后的 query，不要任何解释\n\n"
        f"原始问题：{state['query']}\n"
        "改写后的问题："
    )
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.4,  # 改写需要一点创造性，不能完全是 0
            http_client=make_http_client(),
        )
        new_query = llm.invoke(prompt).content.strip()
        if not new_query:
            new_query = state["query"]  # LLM 返回空就保留原 query
        logger.info("rewrite 改写：%r -> %r（retry=%d）",
                    state["query"], new_query, state.get("retry_count", 0) + 1)
        return {"query": new_query, "retry_count": state.get("retry_count", 0) + 1}
    except Exception:  # noqa: BLE001
        logger.exception("rewrite 调用 LLM 失败，保留原 query")
        return {"query": state["query"], "retry_count": state.get("retry_count", 0) + 1}


def router(state: ChatState) -> dict:
    """D10 意图路由节点：判断问题类型，决定走哪条路。
    - knowledge：需要查知识库
    - chat：闲聊直答
    - tool：需要外部工具（D11 再接真实工具）
    """
    # 前端手动指定了 collection，直接走知识库
    if state.get("collection"):
        logger.info("router 跳过（手动指定 collection=%r）", state["collection"])
        return {"intent": "knowledge"}
    
    if not settings.llm_api_key:
        logger.warning("router 无密钥，默认走知识库")
        return {"intent": "knowledge"}
    
    prompt = (
        "你是问题分类器。判断用户问题属于以下哪一类，只回复类别名称：\n"
        "- knowledge：需要查询知识库/文档/手册/笔记/资料才能回答的问题\n"
        "- chat：闲聊、问候、日常对话（如'你好''谢谢''你是谁'）\n"
        "- tool：需要实时信息或计算（天气、时间、日期、数学计算等）\n\n"
        f"用户问题：{state['query']}\n"
        "类别："
    )
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
            http_client=make_http_client(),
        )
        ans = llm.invoke(prompt).content.strip().lower()
        # 精确匹配优先，包含匹配兜底
        if "knowledge" in ans:
            intent = "knowledge"
        elif "chat" in ans:
            intent = "chat"
        elif "tool" in ans:
            intent = "tool"
        else:
            intent = "knowledge"  # 拿不准时默认走知识库
        logger.info("router 分类=%r | query=%r", intent, state.get("query"))
        return {"intent": intent}
    except Exception:  # noqa: BLE001
        logger.exception("router 调用 LLM 失败，默认走知识库")
        return {"intent": "knowledge"}


def route_by_intent(state: ChatState) -> str:
    """D10 router 后的条件分支：根据 intent 决定走哪条路。"""
    intent = state.get("intent", "knowledge")
    if intent == "chat":
        return "chat_generate"
    if intent == "tool":
        return "tool_select"  # D11：走真实工具流程
    return "route"  # 默认走知识库


def chat_generate(state: ChatState) -> dict:
    """D10 闲聊生成节点：不带 context，直接聊天。"""
    if not settings.llm_api_key:
        return {"answer": f"[mock] 闲聊模式（你说了：{state['query']}）"}
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.5,
            http_client=make_http_client(),
        )
        # 简单闲聊 prompt，可以后续加 history
        prompt = f"你是一个友好的助手。请简短回复用户的问题。\n\n用户：{state['query']}"
        reply = llm.invoke(prompt).content
        logger.info("chat_generate 闲聊回复 | query=%r", state.get("query"))
        return {"answer": reply}
    except Exception:  # noqa: BLE001
        logger.exception("chat_generate 调用 LLM 失败")
        return {"answer": "抱歉，闲聊回复时出错了。"}


def reroute(state: ChatState) -> dict:
    """D9 重路由节点：grade 判 irrelevant 后，换一个还没试过的知识库再查一次。

    不重新跑 route（route 只负责首次选库），直接在剩余库里挑一个，
    把 state.collection 改掉并回到 retrieve，形成「检索后反省 -> 换库重试」的循环。
    """
    tried = list(state.get("tried", []))
    cur = state.get("collection")
    if cur:
        tried.append(cur)  # 把刚查过的库记下来，避免重复查
    # 真实存在的逻辑分类（单一来源，不写死）
    try:
        valid = sorted({
            m["collection"]
            for m in get_collection().get(include=["metadatas"])["metadatas"]
            if m.get("collection")
        })
    except Exception:  # noqa: BLE001
        valid = []
    remaining = [c for c in valid if c not in tried]
    if remaining:
        nxt = remaining[0]
        logger.info("reroute 换库：%r -> %r（retry=%d / 已试=%s）",
                    cur, nxt, state.get("retry_count", 0) + 1, tried)
        return {"collection": nxt, "tried": tried + [nxt],
                "retry_count": state.get("retry_count", 0) + 1}
    # 没更多库可试，放弃重路由，交给 generate 兜底说不知道
    logger.warning("reroute 无更多库可试，放弃（tried=%s）", tried)
    return {"collection": "", "tried": tried,
            "retry_count": state.get("retry_count", 0) + 1}


def route_after_grade(state: ChatState) -> str:
    """grade 后的条件分支：相关直接生成；不相关且还有重试次数就改写 query 重查。"""
    if state.get("grade") == "relevant":
        return "generate"
    if state.get("retry_count", 0) < 2:
        return "rewrite"  # D9：改写 query 重查（检索后反省 / Self-RAG）
    return "generate"  # 重试耗尽，兜底生成（会如实说不知道）


def build_graph():
    """构建并返回编译后的 LangGraph 图。"""
    from langgraph.graph import END, StateGraph

    graph = StateGraph(ChatState)
    # D10：新增 router 入口 + 闲聊分支
    graph.add_node("router", router)
    graph.add_node("chat_generate", chat_generate)
    # D11：工具流程节点
    graph.add_node("tool_select", tool_select)
    graph.add_node("tool_call", tool_call)
    graph.add_node("tool_reflect", tool_reflect)
    # 原有节点
    graph.add_node("route", route)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_node("grade", grade)
    graph.add_node("rewrite", rewrite)  # D9：改写 query 重查
    graph.add_node("grounding", grounding)  # D12：回答前反省
    
    # D10：router 条件边——根据 intent 分流
    graph.add_conditional_edges(
        "router",
        route_by_intent,
        {
            "route": "route",  # knowledge → 走 route 节点
            "chat_generate": "chat_generate",  # chat → 走闲聊
            "tool_select": "tool_select",  # tool → 走工具流程
        },
    )
    graph.add_edge("chat_generate", END)
    
    # D11：工具流程 tool_select → tool_call → tool_reflect → generate
    graph.add_edge("tool_select", "tool_call")
    graph.add_edge("tool_call", "tool_reflect")
    graph.add_edge("tool_reflect", "generate")
    
    # 原有边
    graph.add_edge("route", "retrieve")
    graph.add_edge("retrieve", "grade")
    # D9：grade 后条件分支——相关就生成，不相关且还能重试就改写 query 重查
    graph.add_conditional_edges(
        "grade",
        route_after_grade,
        {"generate": "generate", "rewrite": "rewrite"},
    )
    graph.add_edge("rewrite", "retrieve")  # D9：改写后重新检索（形成循环）
    graph.add_edge("generate", "grounding")  # D12：generate 后走 grounding 校验
    graph.add_edge("grounding", END)  # D12：grounding 后结束
    graph.set_entry_point("router")  # D10：入口改成 router
    return graph.compile()


def run_agent(req: ChatRequest) -> ChatResponse:
    try:
        graph = build_graph()
        result = graph.invoke(
            {
                "query": req.query,
                "history": [m.model_dump() for m in req.history],
                "answer": "",
                "context": [],
                "collection": req.collection,
                "tried": [],
                "intent": "",  # D10：router 写入意图分类
                "tool_name": "",  # D11：工具选择
                "tool_input": "",  # D11：工具入参
                "tool_result": "",  # D11：工具结果
            }
        )
        return ChatResponse(answer=result["answer"], model=settings.llm_model)
    except Exception:  # noqa: BLE001
        # D6·③：先记真实错误，再返回安全兜底
        logger.exception("run_agent 执行失败")
        return ChatResponse(answer="抱歉，服务出错了，请稍后再试。", model="mock")

def route(state: ChatState) -> dict:
    """路由节点：按用户问题用 LLM 自动选知识库，结果写入 state.collection。"""
    # 手动指定了库则跳过分类（可选 override）
    if state.get("collection"):
        return {}
    # 可用库 = 知识库里真实存在的逻辑分类（单一来源，不写死）
    try:
        valid = sorted({
            m["collection"]
            for m in get_collection().get(include=["metadatas"])["metadatas"]
            if m.get("collection")
        })
    except Exception:  # noqa: BLE001
        valid = []
    if not valid or not settings.llm_api_key:
        logger.warning("route 无法路由：valid=%s llm_api_key=%s", valid, bool(settings.llm_api_key))
        return {"collection": ""}

    # 给路由一点"每库里有什么"的线索（读真实文件名，不写死），
    # 否则容易把"刘永庆的电话"误导向 前端（简历 PDF 文件名含"前端"字样）
    try:
        from collections import defaultdict

        sources = defaultdict(set)
        for m in get_collection().get(include=["metadatas"])["metadatas"]:
            if m.get("collection") and m.get("source"):
                sources[m["collection"]].add(m["source"])
        hints = [
            f"- {c}：含文件《{'、'.join(sorted(sources.get(c, []))[:3])}》"
            for c in valid
        ]
        hint_text = "\n".join(hints)
    except Exception:  # noqa: BLE001
        hint_text = ""
    prompt = (
        "你是知识库路由。根据各库包含的文件，只回复以下之一（不要解释）："
        + " / ".join(valid + ["none"])
        + "\n"
        + hint_text
        + f"\n用户问题：{state['query']}"
    )
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
            http_client=make_http_client(),
        )
        ans = llm.invoke(prompt).content.strip()
    except Exception:  # noqa: BLE001
        logger.warning("route 调用 LLM 失败，放弃路由", exc_info=True)
        return {"collection": ""}
    # 数据驱动解析：精确匹配 → 包含匹配 → none（不写死分支）
    chosen = ans if ans in valid else next((c for c in valid if c in ans), "")
    logger.info("route 选定 collection=%r | query=%r", chosen, state.get("query"))
    return {"collection": chosen}
