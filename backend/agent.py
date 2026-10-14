"""个人知识库 Agent：LangGraph 对话图 + 对外 run_agent() + 请求/响应模型。

扁平化后所有 backend 模块都在同一层，互相直接 import（from config / from vector_store ...）。

当前版本：
  route(LLM 自动选知识库) -> retrieve(接 RAG 向量检索 vector_store.query) -> generate(用检索资料拼 prompt 调 LLM)

TODO（面试进阶，自己补）：
  - generate 接真实 LLM（已预留 config，直连智谱）
  - 加工具节点 tool_call + 条件分支
  - 三个反省机制：回答前 / 干活后 / 检索后
"""
import logging

from typing import Literal, TypedDict

from pydantic import BaseModel

from config import make_http_client, settings

from vector_store import get_collection, query as vs_query

logger = logging.getLogger(__name__)

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


def generate(state: ChatState) -> dict:
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


def build_graph():
    """构建并返回编译后的 LangGraph 图。"""
    from langgraph.graph import END, StateGraph

    graph = StateGraph(ChatState)
    graph.add_node("route", route)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge("route", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    graph.set_entry_point("route")   # ← 入口改成 route
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
