"""服务层：编排 Agent 调用，对外暴露 run_agent()。

这里把“Agent 实现(agents/)”和“API 路由(api/)”解耦：
api 只负责收发 HTTP，services 负责业务编排，agents 负责具体智能体逻辑。
"""
from app.agents.graph import build_graph
from app.config import settings
from app.models.chat import ChatRequest, ChatResponse


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
