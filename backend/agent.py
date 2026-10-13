"""个人知识库 Agent：LangGraph 对话图 + 对外 run_agent() + 请求/响应模型。

扁平化后所有 backend 模块都在同一层，互相直接 import（from config / from vector_store ...）。

当前是最小可跑通版本：
  retrieve(占位) -> generate(调用 LLM，无密钥则 mock)

TODO（面试核心，自己补）：
  - retrieve 接 RAG 向量检索（调 vector_store.query）
  - generate 接真实 LLM（已预留 config）
  - 加工具节点 tool_call + 条件分支
  - 三个反省机制：回答前 / 干活后 / 检索后
"""
from typing import Literal, TypedDict

from pydantic import BaseModel

from config import make_http_client, settings


# ---------- 请求 / 响应模型 ----------
class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    query: str
    history: list[Message] = []


class ChatResponse(BaseModel):
    answer: str
    model: str = "mock"


# ---------- 智能体图 ----------
class ChatState(TypedDict):
    query: str
    history: list[dict]
    answer: str


def retrieve(state: ChatState) -> dict:
    # TODO: 在这里做 RAG 召回（向量库查询 + 重排），见 vector_store.query
    return {}


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
            reply = llm.invoke(state["query"]).content
            return {"answer": reply}
        except Exception:  # noqa: BLE001
            pass
    return {"answer": f"[mock] 你问了：{state['query']}（未配置 LLM_API_KEY，返回占位回答）"}


def build_graph():
    """构建并返回编译后的 LangGraph 图。"""
    from langgraph.graph import END, StateGraph

    graph = StateGraph(ChatState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    graph.set_entry_point("retrieve")
    return graph.compile()


def run_agent(req: ChatRequest) -> ChatResponse:
    try:
        graph = build_graph()
        result = graph.invoke(
            {
                "query": req.query,
                "history": [m.model_dump() for m in req.history],
                "answer": "",
            }
        )
        return ChatResponse(answer=result["answer"], model=settings.llm_model)
    except Exception:  # noqa: BLE001
        # 兜底：没配 LLM 密钥 / 依赖缺失时也能跑通，返回 mock 回答
        return ChatResponse(answer=f"[mock] 你问了：{req.query}", model="mock")
