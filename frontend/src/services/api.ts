// 后端 API 调用封装
// 默认 BASE_URL 为空，走 vite 的 /api 代理转发到后端 8000（本地与 docker 都通用）
const BASE_URL = import.meta.env.VITE_API_BASE ?? "";

import type { ChatRequest, ChatResponse } from "../types/chat";

export async function chat(req: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`请求失败: ${res.status}`);
  }
  return res.json();
}

export async function healthCheck(): Promise<{
  status: string;
  message?: string;
}> {
  const res = await fetch(`${BASE_URL}/api/health`);
  if (!res.ok) {
    throw new Error(`请求失败: ${res.statusText}`);
  }
  return res.json();
}
