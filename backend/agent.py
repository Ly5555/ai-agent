"""个人知识库 Agent：LangGraph 对话图 + 对外 run_agent() + 请求/响应模型。

扁平化后所有 backend 模块都在同一层，互相直接 import（from config / from vector_store ...）。

当前版本：
  route(LLM 自动选知识库) -> retrieve(接 RAG 向量检索 vector_store.query) -> generate(用检索资料拼 prompt 调 LLM)

TODO（面试进阶，自己补）：
  - generate 接真实 LLM（已预留 config，直连智谱）
  - 加工具节点 tool_call + 条件分支
  - 三个反省机制：回答前 / 干活后 / 检索后
"""
from typing import Literal, TypedDict

from pydantic import BaseModel

from config import make_http_client, settings

from vector_store import get_collection, query as vs_query

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
    if not collection:
        return {"context": []}
    hits = vs_query(state["query"], collection, top_k=4)
    return {"context": [h["text"] for h in hits]}


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
            # 把检索到的资料拼进 prompt，让 LLM 基于文档回答（RAG 接通）
            ctx = "\n".join(state.get("context", []))
            prompt = (
                "根据以下资料回答问题，资料中没有的信息如实说不知道：\n"
                f"{ctx}\n\n问题：{state['query']}"
            )
            reply = llm.invoke(prompt).content
            return {"answer": reply}
        except Exception:  # noqa: BLE001
            pass
    return {"answer": f"[mock] 你问了：{state['query']}（未配置 LLM_API_KEY，返回占位回答）"}


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
        # 兜底：没配 LLM 密钥 / 依赖缺失时也能跑通，返回 mock 回答
        return ChatResponse(answer=f"[mock] 你问了：{req.query}", model="mock")

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
        return {"collection": ""}

    prompt = (
        "你是知识库路由。只回复以下之一（不要解释）："
        + " / ".join(valid + ["none"])
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
        return {"collection": ""}
    # 数据驱动解析：精确匹配 → 包含匹配 → none（不写死分支）
    chosen = ans if ans in valid else next((c for c in valid if c in ans), "")
    return {"collection": chosen}
