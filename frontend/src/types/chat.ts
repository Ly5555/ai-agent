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
