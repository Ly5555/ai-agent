"""请求 / 响应数据模型（Pydantic v2）。"""
from typing import Literal

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    query: str
    history: list[Message] = []


class ChatResponse(BaseModel):
    answer: str
    model: str = "mock"
