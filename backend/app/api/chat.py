"""聊天相关路由：/api/chat、/api/health。"""
from fastapi import APIRouter

from app.models.chat import ChatRequest, ChatResponse
from app.services.agent_service import run_agent

router = APIRouter(prefix="/api", tags=["chat"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "message": "FastAPI 后端服务启动成功！"}


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    return run_agent(req)
