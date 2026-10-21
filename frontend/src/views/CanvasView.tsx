import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import ReactFlow, {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  type Edge,
  type Node,
  type NodeProps,
} from "reactflow";
import "reactflow/dist/style.css";
import { Tag, Spin, Empty, Button } from "antd";
import { ClearOutlined, MessageOutlined, ApartmentOutlined } from "@ant-design/icons";
import { getGraph, loadTraces, clearTraces } from "../services/api";
import type { GraphData, NodeType, TraceRecord } from "../types/chat";

// 节点类型 → 配色 / 中文名
const TYPE_STYLE: Record<NodeType, { color: string; label: string }> = {
  entry: { color: "#52c41a", label: "入口" },
  exit: { color: "#8c8c8c", label: "出口" },
  decision: { color: "#fa8c16", label: "路由" },
  retrieval: { color: "#1677ff", label: "检索" },
  reflection: { color: "#722ed1", label: "反省" },
  tool: { color: "#13c2c2", label: "工具" },
  generation: { color: "#eb2f96", label: "生成" },
  process: { color: "#595959", label: "处理" },
};

interface AgentNodeData {
  label: string;
  desc: string;
  nodeType: NodeType;
  active: boolean;
  dimmed: boolean;
  order: number | null;
  visits: number;
}

// 自定义节点：左侧色条 + 类型角标 + 命中轨迹时高亮并标序号
function AgentNode({ data }: NodeProps<AgentNodeData>) {
  const cfg = TYPE_STYLE[data.nodeType] ?? TYPE_STYLE.process;
  return (
    <div
      title={data.desc}
      style={{
        width: 200,
        padding: "8px 10px 8px 14px",
        background: data.active ? "#fff" : data.dimmed ? "#fafafa" : "#fff",
        border: `1px solid ${data.active ? cfg.color : data.dimmed ? "#eee" : "#e0e0e0"}`,
        borderLeft: `4px solid ${cfg.color}`,
        borderRadius: 8,
        opacity: data.dimmed ? 0.35 : 1,
        boxShadow: data.active ? `0 0 0 3px ${cfg.color}33, 0 2px 8px rgba(0,0,0,0.08)` : "none",
        transition: "all 160ms ease",
      }}
    >
      {/* 四个把手全部显式命名：多把手时不指定 id 会默认取 DOM 里的第一个，
          加把手就可能把普通边的出口悄悄改掉 */}
      <Handle id="t-left" type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle id="t-top" type="target" position={Position.Top} style={{ opacity: 0 }} />
      <Handle id="s-right" type="source" position={Position.Right} style={{ opacity: 0 }} />
      {/* 回边专用：从下方出、从上方入，绕到行的下面走，
          否则右→左的 smoothstep 会画成一截断头线 */}
      <Handle id="s-bottom" type="source" position={Position.Bottom} style={{ opacity: 0 }} />
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "#222" }}>{data.label}</span>
        {data.order !== null && (
          <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 3 }}>
            {data.visits > 1 && (
              <span
                title={`该节点本次被执行 ${data.visits} 次（反省循环）`}
                style={{
                  fontSize: 10,
                  lineHeight: "14px",
                  padding: "0 4px",
                  borderRadius: 7,
                  color: cfg.color,
                  background: `${cfg.color}1a`,
                  fontWeight: 600,
                }}
              >
                ×{data.visits}
              </span>
            )}
            <span
              style={{
                minWidth: 18,
                height: 18,
                lineHeight: "18px",
                textAlign: "center",
                borderRadius: 9,
                fontSize: 11,
                color: "#fff",
                background: cfg.color,
              }}
            >
              {data.order}
            </span>
          </span>
        )}
      </div>
      <div style={{ fontSize: 10, color: "#999", marginTop: 2 }}>{data.desc}</div>
      <div style={{ fontSize: 10, color: cfg.color, marginTop: 3 }}>{cfg.label}</div>
    </div>
  );
}

const nodeTypes = { agent: AgentNode };

function fmtTime(ts: number) {
  const d = new Date(ts);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export default function CanvasView() {
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [error, setError] = useState("");
  const [traces, setTraces] = useState<TraceRecord[]>([]);
  const [selected, setSelected] = useState<TraceRecord | null>(null);

  // 首次进入：拉真实拓扑 + 读本地执行记录；?trace=ts 直接从对话页定位到那条路径
  useEffect(() => {
    setTraces(loadTraces());
    getGraph()
      .then(setGraph)
      .catch((e: Error) => setError(e.message));

    const ts = new URLSearchParams(window.location.search).get("trace");
    if (ts) {
      const hit = loadTraces().find((t) => String(t.ts) === ts);
      if (hit) setSelected(hit);
    }
  }, []);

  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [] as Node[], edges: [] as Edge[] };

    const path = selected?.trace ?? [];
    const hasSelection = path.length > 0;

    // 轨迹里同一节点可能走多次（反省循环），序号取首次出现位置
    const order = new Map<string, number>();
    path.forEach((nid, i) => {
      if (!order.has(nid)) order.set(nid, i + 1);
    });
    const activeNodes = new Set(path);
    // 反省循环会让同一节点跑多次，统计次数用于 ×N 角标
    const visits = new Map<string, number>();
    path.forEach((nid) => visits.set(nid, (visits.get(nid) ?? 0) + 1));
    if (hasSelection) {
      activeNodes.add("__start__");
      activeNodes.add("__end__");
    }

    const rfNodes: Node[] = graph.nodes.map((n) => ({
      id: n.id,
      type: "agent",
      position: n.position,
      data: {
        label: n.label,
        desc: n.desc,
        nodeType: n.type,
        active: activeNodes.has(n.id),
        dimmed: hasSelection && !activeNodes.has(n.id),
        order: order.get(n.id) ?? null,
        visits: visits.get(n.id) ?? 0,
      } satisfies AgentNodeData,
    }));

    // 连续两个节点之间的边视为本次走过的路径
    const usedEdges = new Set<string>();
    for (let i = 0; i < path.length - 1; i++) usedEdges.add(`${path[i]}->${path[i + 1]}`);
    if (path.length > 0) {
      usedEdges.add(`__start__->${path[0]}`);
      usedEdges.add(`${path[path.length - 1]}->__end__`);
    }

    const rfEdges: Edge[] = graph.edges.map((e) => {
      const onPath = usedEdges.has(e.id);
      const color = onPath ? (e.isBack ? "#722ed1" : "#1677ff") : "#c9c9c9";
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        // 全部显式指定把手：回边（右→左）走「下出上入」绕道，避免断头线
        sourceHandle: e.isBack ? "s-bottom" : "s-right",
        targetHandle: e.isBack ? "t-top" : "t-left",
        ...(e.isBack ? { pathOptions: { offset: 48 } } : {}),
        label: e.label || undefined,
        type: "smoothstep",
        animated: onPath,
        style: {
          stroke: color,
          strokeWidth: onPath ? 2.2 : 1.2,
          strokeDasharray: e.conditional || e.isBack ? "5 4" : undefined,
          opacity: hasSelection && !onPath ? 0.25 : 1,
        },
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 14, height: 14 },
        labelStyle: { fontSize: 10, fill: onPath ? color : "#8c8c8c" },
        labelBgStyle: { fill: "#fff", fillOpacity: 0.85 },
        labelBgPadding: [3, 1] as [number, number],
        labelBgBorderRadius: 3,
      };
    });

    return { nodes: rfNodes, edges: rfEdges };
  }, [graph, selected]);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#f7f8fa" }}>
      {/* 顶部栏 */}
      <div
        style={{
          padding: "10px 16px",
          background: "#fff",
          borderBottom: "1px solid #eef0f3",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <ApartmentOutlined style={{ fontSize: 18, color: "#1677ff" }} />
        <span style={{ fontSize: 15, fontWeight: 600 }}>Agent 工作流</span>
        <span style={{ fontSize: 11, color: "#999" }}>
          {graph ? `${graph.nodes.length} 个节点 · ${graph.edges.length} 条边（后端真实拓扑）` : "加载中…"}
        </span>
        {/* 类型图例 */}
        <div style={{ display: "flex", gap: 6, marginLeft: 8, flexWrap: "wrap" }}>
          {(Object.keys(TYPE_STYLE) as NodeType[])
            .filter((k) => k !== "process")
            .map((k) => (
              <span key={k} style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 10, color: "#666" }}>
                <i style={{ width: 8, height: 8, borderRadius: 2, background: TYPE_STYLE[k].color, display: "inline-block" }} />
                {TYPE_STYLE[k].label}
              </span>
            ))}
        </div>
        <Link to="/chat" style={{ marginLeft: "auto" }}>
          <Button size="small" type="primary" ghost icon={<MessageOutlined />}>
            返回对话页
          </Button>
        </Link>
      </div>

      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* 画布 */}
        <div style={{ flex: 1, position: "relative" }}>
          {error ? (
            <Empty
              description={`后端未连接：${error}`}
              style={{ padding: "80px 0" }}
            >
              <p style={{ color: "#999", fontSize: 12 }}>启动命令：cd backend && uvicorn main:app --reload --port 8000</p>
            </Empty>
          ) : !graph ? (
            <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 10 }}>
              <Spin />
              <span style={{ color: "#999", fontSize: 12 }}>正在读取工作流拓扑…</span>
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              nodesDraggable={false}
              nodesConnectable={false}
              proOptions={{ hideAttribution: true }}
            >
              <Controls showInteractive={false} />
              <Background color="#dcdfe6" gap={20} />
            </ReactFlow>
          )}
        </div>

        {/* 右侧执行记录 */}
        <div
          style={{
            width: 280,
            background: "#fff",
            borderLeft: "1px solid #eef0f3",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <div style={{ padding: "10px 12px", borderBottom: "1px solid #f0f0f0", display: "flex", alignItems: "center" }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>执行轨迹</span>
            <span style={{ fontSize: 10, color: "#999", marginLeft: 6 }}>点击高亮该次路径</span>
            {traces.length > 0 && (
              <Button
                size="small"
                type="text"
                icon={<ClearOutlined style={{ fontSize: 11 }} />}
                style={{ marginLeft: "auto", fontSize: 11, height: 22 }}
                onClick={() => {
                  clearTraces();
                  setTraces([]);
                  setSelected(null);
                }}
              >
                清空
              </Button>
            )}
          </div>

          <div style={{ flex: 1, overflow: "auto", padding: 8 }}>
            {selected && (
              <div style={{ fontSize: 11, color: "#666", background: "#f0f6ff", border: "1px solid #d6e6ff", borderRadius: 6, padding: "6px 8px", marginBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 4 }}>
                  <Tag color="blue" style={{ margin: 0, fontSize: 10, lineHeight: "16px" }}>
                    {selected.intent || "knowledge"}
                  </Tag>
                  <span style={{ color: "#999", fontSize: 10 }}>{fmtTime(selected.ts)}</span>
                  <a style={{ marginLeft: "auto", fontSize: 10 }} onClick={() => setSelected(null)}>
                    取消高亮
                  </a>
                </div>
                <div style={{ fontWeight: 600, marginBottom: 4, color: "#333" }}>{selected.query}</div>
                <div style={{ lineHeight: 1.7 }}>
                  {selected.trace.map((nid, i) => {
                    const found = graph?.nodes.find((n) => n.id === nid);
                    const color = TYPE_STYLE[(found?.type ?? "process") as NodeType]?.color ?? "#595959";
                    return (
                      <span key={`${nid}-${i}`}>
                        <span style={{ fontSize: 11, color }}>{found?.label ?? nid}</span>
                        {i < selected.trace.length - 1 && <span style={{ color: "#ccc", margin: "0 3px" }}>→</span>}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}

            {traces.length === 0 && !selected ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={<span style={{ fontSize: 11 }}>还没有执行记录<br />去知识库问一个问题试试</span>}
                style={{ padding: "40px 0" }}
              />
            ) : (
              traces.map((t) => {
                const isActive = selected?.ts === t.ts;
                return (
                  <div
                    key={t.ts}
                    className="trace-item"
                    onClick={() => setSelected(isActive ? null : t)}
                    style={{
                      padding: "8px 10px",
                      borderRadius: 6,
                      cursor: "pointer",
                      marginBottom: 6,
                      background: isActive ? "#e6f0ff" : "#fafafa",
                      border: `1px solid ${isActive ? "#1677ff" : "transparent"}`,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <Tag style={{ margin: 0, fontSize: 10, lineHeight: "15px" }} color={isActive ? "blue" : "default"}>
                        {t.intent || "—"}
                      </Tag>
                      <span style={{ fontSize: 10, color: "#999", marginLeft: "auto" }}>{fmtTime(t.ts)}</span>
                    </div>
                    <div style={{ fontSize: 12, color: "#333", marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {t.query}
                    </div>
                    <div style={{ fontSize: 10, color: "#999", marginTop: 2 }}>{t.trace.length} 个节点</div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
