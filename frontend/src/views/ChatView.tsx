import { useRef, useState } from "react";
import { chat, uploadDocument } from "../services/api";
import type { Message } from "../types/chat";

export default function ChatView() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [collection, setCollection] = useState("简历");
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function upload() {
    if (files.length === 0 || !collection.trim() || uploading) return;
    setUploading(true);
    setUploadStatus("");
    let okCount = 0;
    let totalChunks = 0;
    const failures: string[] = [];
    // 多选：逐个文件调用现有单文件上传接口，单个失败不影响其它文件
    for (const f of files) {
      try {
        const result = await uploadDocument(f, collection.trim());
        okCount += 1;
        totalChunks += result.chunks;
      } catch (error) {
        failures.push(`${f.name}：${(error as Error).message}`);
      }
    }
    if (failures.length > 0) {
      setUploadStatus(
        `成功 ${okCount} 个、共 ${totalChunks} 块；失败 ${failures.length} 个 → ${failures.join("；")}`,
      );
    } else {
      setUploadStatus(`已上传 ${okCount} 个文件，共拆分为 ${totalChunks} 个知识片段。`);
    }
    setFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = ""; // 清空 input，便于重复选同一文件
    setUploading(false);
  }

  async function send() {
    const q = input.trim();
    if (!q || loading) return;

    const next: Message[] = [...messages, { role: "user", content: q }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const res = await chat({ query: q, history: next });
      setMessages([...next, { role: "assistant", content: res.answer }]);
    } catch (e) {
      setMessages([
        ...next,
        { role: "assistant", content: `出错了：${(e as Error).message}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 720, margin: "40px auto", fontFamily: "system-ui" }}>
      <h1>个人知识库 Agent</h1>
      <p style={{ color: "#666" }}>基于你的笔记和文档回答，并在后续版本提供来源引用。</p>
      <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
        <input
          value={collection}
          onChange={(event) => setCollection(event.target.value)}
          aria-label="知识分类"
          placeholder="知识分类，例如 Python学习笔记"
          style={{ width: 190, padding: 8 }}
        />
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.md,.txt"
          onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
        />
        <button
          style={{ padding: "8px 16px" }}
          onClick={upload}
          disabled={files.length === 0 || uploading}
        >
          {uploading ? "入库中…" : files.length > 1 ? `上传 ${files.length} 个文件` : "上传资料"}
        </button>
      </div>
      {files.length > 0 && !uploading && (
        <p style={{ color: "#666", fontSize: 12, marginTop: -8, marginBottom: 12 }}>
          已选 {files.length} 个：{files.map((f) => f.name).join("、")}
        </p>
      )}
      {uploadStatus && (
        <p
          style={{
            color: uploadStatus.includes("失败") ? "#b42318" : "#2d7a46",
          }}
        >
          {uploadStatus}
        </p>
      )}
      <div
        style={{
          border: "1px solid #ddd",
          borderRadius: 8,
          padding: 16,
          minHeight: 240,
        }}
      >
        {messages.length === 0 && (
          <p style={{ color: "#999" }}>
            可以问：“帮我总结 Python 学习笔记”或“JSON 文件记忆怎么实现？”
          </p>
        )}
        {messages.map((m, i) => (
          <p key={i}>
            <b>{m.role === "user" ? "你" : "Agent"}：</b>
            {m.content}
          </p>
        ))}
        {loading && <p style={{ color: "#999" }}>思考中…</p>}
      </div>
      <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
        <input
          style={{ flex: 1, padding: 8 }}
          value={input}
          placeholder="向你的知识库提问"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button style={{ padding: "8px 16px" }} onClick={send} disabled={loading}>
          发送
        </button>
      </div>
    </div>
  );
}
