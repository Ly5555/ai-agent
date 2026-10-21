// 后端 API 调用封装
// 默认 BASE_URL 为空，走 vite 的 /api 代理转发到后端 8000（本地与 docker 都通用）
const BASE_URL = import.meta.env.VITE_API_BASE ?? "";

import type { ChatRequest, ChatResponse, CollectionInfo, DocumentDetail, GraphData, TraceRecord, UploadResponse } from "../types/chat";

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

export function uploadDocument(
  file: File,
  collection: string,
  onProgress?: (percent: number) => void,
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const body = new FormData();
    body.append("file", file);
    body.append("collection", collection);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE_URL}/api/upload`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error("解析响应失败"));
        }
      } else {
        let msg = `上传失败: ${xhr.status}`;
        try {
          const detail = JSON.parse(xhr.responseText);
          if (detail.detail) msg = detail.detail;
        } catch {}
        reject(new Error(msg));
      }
    };

    xhr.onerror = () => reject(new Error("网络错误"));
    xhr.send(body);
  });
}

export async function getCollections(): Promise<CollectionInfo[]> {
  const res = await fetch(`${BASE_URL}/api/collections`);
  if (!res.ok) {
    throw new Error(`请求失败: ${res.status}`);
  }
  return res.json();
}

export async function getDocuments(collectionName: string): Promise<DocumentDetail[]> {
  const res = await fetch(`${BASE_URL}/api/collections/${encodeURIComponent(collectionName)}/documents`);
  if (!res.ok) {
    throw new Error(`请求失败: ${res.status}`);
  }
  return res.json();
}

export async function getRawDocument(collectionName: string, filename: string): Promise<{ filename: string; collection: string; content: string }> {
  const res = await fetch(`${BASE_URL}/api/collections/${encodeURIComponent(collectionName)}/raw/${encodeURIComponent(filename)}`);
  if (!res.ok) {
    throw new Error(`请求失败: ${res.status}`);
  }
  return res.json();
}

export async function moveDocument(sourceCollection: string, filename: string, targetCollection: string): Promise<{ message: string; chunks: number }> {
  const res = await fetch(`${BASE_URL}/api/documents/move`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_collection: sourceCollection,
      filename,
      target_collection: targetCollection,
    }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `移动失败: ${res.status}`);
  }
  return res.json();
}

export async function deleteDocument(collection: string, filename: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/api/documents/delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ collection, filename }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `删除失败: ${res.status}`);
  }
  return res.json();
}

export async function createCollection(name: string, icon?: string, color?: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/api/collections/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, icon: icon || "BookOutlined", color: color || "#1677ff" }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `创建失败: ${res.status}`);
  }
  return res.json();
}

export async function renameCollection(oldName: string, newName: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/api/collections/rename`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ old_name: oldName, new_name: newName }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `重命名失败: ${res.status}`);
  }
  return res.json();
}

export async function deleteCollection(name: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/api/collections/delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `删除失败: ${res.status}`);
  }
  return res.json();
}

export async function updateCollectionIcon(name: string, icon?: string, color?: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/api/collections/update-icon`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, icon: icon || "", color: color || "" }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `更新图标失败: ${res.status}`);
  }
  return res.json();
}

// ---- D14：真实拓扑 + 执行轨迹 ----

export async function getGraph(): Promise<GraphData> {
  const res = await fetch(`${BASE_URL}/api/graph`);
  if (!res.ok) {
    throw new Error(`获取工作流拓扑失败: ${res.status}`);
  }
  return res.json();
}

const TRACE_KEY = "agent_traces";
const TRACE_LIMIT = 20;

export function loadTraces(): TraceRecord[] {
  try {
    const raw = localStorage.getItem(TRACE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveTrace(record: TraceRecord): TraceRecord[] {
  const next = [record, ...loadTraces()].slice(0, TRACE_LIMIT);
  try {
    localStorage.setItem(TRACE_KEY, JSON.stringify(next));
  } catch {
    /* 存储满就放弃持久化，不影响本次会话 */
  }
  return next;
}

export function clearTraces(): void {
  localStorage.removeItem(TRACE_KEY);
}
