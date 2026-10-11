import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import ReactFlow, { Background, Controls } from "reactflow";
import "reactflow/dist/style.css";
import { healthCheck } from "../services/api";

// 工作流画布（首页）：顶部状态栏实时检测后端连通性
export default function CanvasView() {
  const [status, setStatus] = useState("正在连接后端...");

  useEffect(() => {
    async function testBackend() {
      try {
        const data = await healthCheck();
        setStatus(`🚀 后端连接成功！状态: ${data.status}`);
      } catch (error: any) {
        setStatus(
          `⚠️ 后端连接失败: ${error?.message}（请确认后端已启动：cd backend && uvicorn main:app --reload）`,
        );
      }
    }
    testBackend();
  }, []);

  const initialNodes = [
    { id: "1", position: { x: 250, y: 5 }, data: { label: "输入节点 (Start)" } },
    { id: "2", position: { x: 100, y: 100 }, data: { label: "AI Agent 节点" } },
    { id: "3", position: { x: 400, y: 100 }, data: { label: "工具调用节点" } },
  ];

  const initialEdges = [
    { id: "e1-2", source: "1", target: "2" },
    { id: "e1-3", source: "1", target: "3" },
  ];

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <div
        style={{
          padding: "15px",
          background: "#1e1e1e",
          color: "#fff",
          borderBottom: "1px solid #333",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <p style={{ margin: 0, fontSize: "14px" }}>{status}</p>
        <Link to="/chat" style={{ color: "#4da3ff", fontSize: "14px" }}>
          去聊天 →
        </Link>
      </div>
      <div style={{ flex: 1 }}>
        <ReactFlow nodes={initialNodes} edges={initialEdges} fitView>
          <Controls />
          <Background />
        </ReactFlow>
      </div>
    </div>
  );
}
