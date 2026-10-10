import { useState } from "react";
import { chat } from "../services/api";
import type { Message } from "../types/chat";

export default function ChatView() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

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
      <h1>AI Knowledge Agent</h1>
      <div
        style={{
          border: "1px solid #ddd",
          borderRadius: 8,
          padding: 16,
          minHeight: 240,
        }}
      >
        {messages.length === 0 && <p style={{ color: "#999" }}>开始对话吧～</p>}
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
          placeholder="输入你的问题"
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
