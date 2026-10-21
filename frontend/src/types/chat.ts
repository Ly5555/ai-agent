export type Role = "user" | "assistant" | "system";

export interface Message {
  role: Role;
  content: string;
}

export interface ChatRequest {
  query: string;
  history: Message[];
}

export interface ChatResponse {
  answer: string;
  model: string;
  intent?: string;
  trace?: string[];
}

// 聊天室内展示的消息：比发给后端的 Message 多了执行轨迹元信息
export interface ChatMessage extends Message {
  intent?: string;
  trace?: string[];
  traceTs?: number;
}

// 一次问答的执行记录，写入 localStorage 供画布页高亮
export interface TraceRecord {
  query: string;
  intent: string;
  trace: string[];
  ts: number;
}

export type NodeType =
  | "entry"
  | "exit"
  | "decision"
  | "retrieval"
  | "reflection"
  | "tool"
  | "generation"
  | "process";

export interface GraphNode {
  id: string;
  label: string;
  type: NodeType;
  desc: string;
  position: { x: number; y: number };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  conditional: boolean;
  isBack: boolean;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface UploadResponse {
  message: string;
  collection: string;
  filename: string;
  chunks: number;
}

export interface CollectionInfo {
  name: string;
  documents: string[];
  total_chunks: number;
  icon: string;
  color: string;
}

export interface DocumentDetail {
  source: string;
  page: number | null;
  text: string;
  score: number;
}
