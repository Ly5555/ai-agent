"""LangGraph 智能体图定义。

当前是最小可跑通版本：
  retrieve(占位) -> generate(调用 LLM，无密钥则 mock)

TODO（面试核心，自己补）：
  - retrieve 接 RAG 向量检索
  - generate 接真实 LLM（已预留 config）
  - 加工具节点 tool_call + 条件分支
"""
from typing import TypedDict

from app.config import settings


class ChatState(TypedDict):
    query: str
    history: list[dict]
    answer: str


def retrieve(state: ChatState) -> dict:
    # TODO: 在这里做 RAG 召回（向量库查询 + 重排）
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
