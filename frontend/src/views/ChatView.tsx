import { useRef, useState, useEffect } from "react";
import { Upload, Button, Input, message, Card, Tag, Empty, Spin, Avatar, Divider, Progress, Popconfirm, Modal } from "antd";
import {
  SendOutlined,
  UploadOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  MessageOutlined,
  FolderOutlined,
  BookOutlined,
  FileMarkdownOutlined,
  FilePdfOutlined,
  FileTextOutlined as FileIcon,
  DeleteOutlined,
  PlusOutlined,
  EditOutlined,
  CodeOutlined,
  GlobalOutlined,
  StarOutlined,
  HeartOutlined,
  CloudOutlined,
  ReadOutlined,
  ExperimentOutlined,
  TrophyOutlined,
  SafetyOutlined,
  ApiOutlined,
  AppstoreOutlined,
  BellOutlined,
  BulbOutlined,
  CameraOutlined,
  CarOutlined,
  CrownOutlined,
  DesktopOutlined,
  EnvironmentOutlined,
  FireOutlined,
  GiftOutlined,
  HistoryOutlined,
  InsuranceOutlined,
  LayoutOutlined,
  LaptopOutlined,
  MobileOutlined,
  NotificationOutlined,
  PhoneOutlined,
  PictureOutlined,
  RocketOutlined,
  ScheduleOutlined,
  ShoppingOutlined,
  SmileOutlined,
  SoundOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  ToolOutlined,
  VideoCameraOutlined,
  WalletOutlined,
  WifiOutlined,
} from "@ant-design/icons";
import type { UploadFile } from "antd/es/upload/interface";
import { chat, uploadDocument, getCollections, getRawDocument, moveDocument, deleteDocument, createCollection, renameCollection, deleteCollection, updateCollectionIcon } from "../services/api";
import type { Message, CollectionInfo } from "../types/chat";

const { TextArea } = Input;

// 根据文件扩展名返回图标
function getFileIcon(filename: string) {
  const ext = filename.toLowerCase().split(".").pop();
  if (ext === "pdf") return <FilePdfOutlined style={{ color: "#ff4d4f" }} />;
  if (ext === "md") return <FileMarkdownOutlined style={{ color: "#1677ff" }} />;
  return <FileIcon style={{ color: "#52c41a" }} />;
}

// 知识库可选图标
const ICON_OPTIONS = [
  { key: "BookOutlined", icon: <BookOutlined /> },
  { key: "CodeOutlined", icon: <CodeOutlined /> },
  { key: "GlobalOutlined", icon: <GlobalOutlined /> },
  { key: "StarOutlined", icon: <StarOutlined /> },
  { key: "HeartOutlined", icon: <HeartOutlined /> },
  { key: "CloudOutlined", icon: <CloudOutlined /> },
  { key: "FolderOutlined", icon: <FolderOutlined /> },
  { key: "ReadOutlined", icon: <ReadOutlined /> },
  { key: "ExperimentOutlined", icon: <ExperimentOutlined /> },
  { key: "TrophyOutlined", icon: <TrophyOutlined /> },
  { key: "SafetyOutlined", icon: <SafetyOutlined /> },
  { key: "ApiOutlined", icon: <ApiOutlined /> },
  { key: "AppstoreOutlined", icon: <AppstoreOutlined /> },
  { key: "BellOutlined", icon: <BellOutlined /> },
  { key: "BulbOutlined", icon: <BulbOutlined /> },
  { key: "CameraOutlined", icon: <CameraOutlined /> },
  { key: "CarOutlined", icon: <CarOutlined /> },
  { key: "CrownOutlined", icon: <CrownOutlined /> },
  { key: "DesktopOutlined", icon: <DesktopOutlined /> },
  { key: "EnvironmentOutlined", icon: <EnvironmentOutlined /> },
  { key: "FireOutlined", icon: <FireOutlined /> },
  { key: "GiftOutlined", icon: <GiftOutlined /> },
  { key: "HistoryOutlined", icon: <HistoryOutlined /> },
  { key: "LayoutOutlined", icon: <LayoutOutlined /> },
  { key: "LaptopOutlined", icon: <LaptopOutlined /> },
  { key: "MobileOutlined", icon: <MobileOutlined /> },
  { key: "PictureOutlined", icon: <PictureOutlined /> },
  { key: "RocketOutlined", icon: <RocketOutlined /> },
  { key: "ScheduleOutlined", icon: <ScheduleOutlined /> },
  { key: "ShoppingOutlined", icon: <ShoppingOutlined /> },
  { key: "SmileOutlined", icon: <SmileOutlined /> },
  { key: "SoundOutlined", icon: <SoundOutlined /> },
  { key: "TeamOutlined", icon: <TeamOutlined /> },
  { key: "ThunderboltOutlined", icon: <ThunderboltOutlined /> },
  { key: "ToolOutlined", icon: <ToolOutlined /> },
  { key: "VideoCameraOutlined", icon: <VideoCameraOutlined /> },
  { key: "WalletOutlined", icon: <WalletOutlined /> },
  { key: "WifiOutlined", icon: <WifiOutlined /> },
];

// 可选颜色
const COLOR_OPTIONS = [
  "#1677ff", "#52c41a", "#faad14", "#ff4d4f", "#722ed1",
  "#13c2c2", "#eb2f96", "#fa8c16", "#2f54eb", "#a0d911",
];

function getCollectionIcon(iconKey: string) {
  const opt = ICON_OPTIONS.find((o) => o.key === iconKey);
  return opt ? opt.icon : <BookOutlined />;
}

export default function ChatView() {
  const [activeView, setActiveView] = useState<"chat" | "knowledge">("chat");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({ current: 0, total: 0, filename: "", percent: 0 });

  // 知识库相关状态
  const [collections, setCollections] = useState<CollectionInfo[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(false);
  const [selectedCollection, setSelectedCollection] = useState<string | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<string | null>(null);
  const [rawContent, setRawContent] = useState<string>("");
  const [contentLoading, setContentLoading] = useState(false);
  const [dragOverTarget, setDragOverTarget] = useState<string | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newIcon, setNewIcon] = useState("BookOutlined");
  const [newColor, setNewColor] = useState("#1677ff");
  const [renaming, setRenaming] = useState<string | null>(null); // 正在重命名的分类名
  const [renameValue, setRenameValue] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  // 加载知识库列表
  useEffect(() => {
    loadCollections();
  }, []);

  // 上传文件
  async function handleUpload() {
    if (fileList.length === 0 || uploading) return;
    setUploading(true);

    // 从 fileList 中提取原始 File 对象
    const files: File[] = [];
    for (const f of fileList) {
      if (f.originFileObj) {
        files.push(f.originFileObj);
      } else if (f instanceof File) {
        files.push(f);
      }
    }

    setUploadProgress({ current: 0, total: files.length, filename: "", percent: 0 });

    let okCount = 0;
    let totalChunks = 0;
    const failures: string[] = [];

    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      setUploadProgress({ current: i + 1, total: files.length, filename: f.name, percent: 0 });
      
      try {
        const result = await uploadDocument(f, "", (pct) => {
          setUploadProgress((prev) => ({ ...prev, percent: pct }));
        });
        okCount += 1;
        totalChunks += result.chunks;
        message.success(`${f.name} 入库成功（${result.chunks} 块）`);
      } catch (error) {
        failures.push(`${f.name}：${(error as Error).message}`);
        message.error(`${f.name} 上传失败`);
      }
    }

    if (failures.length > 0) {
      message.warning(`成功 ${okCount} 个，失败 ${failures.length} 个`);
    } else if (okCount > 0) {
      message.success(`已上传 ${okCount} 个文件，共 ${totalChunks} 块`);
    }

    setFileList([]);
    setUploading(false);
    setUploadProgress({ current: 0, total: 0, filename: "", percent: 0 });

    // 刷新知识库列表
    if (okCount > 0) {
      loadCollections();
    }
  }

  // 发送消息
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
      message.error("发送失败");
    } finally {
      setLoading(false);
    }
  }

  // 加载知识库列表
  async function loadCollections() {
    setCollectionsLoading(true);
    try {
      const data = await getCollections();
      setCollections(data);
    } catch (e) {
      message.error("加载知识库失败");
    } finally {
      setCollectionsLoading(false);
    }
  }

  // 查看知识库（显示文档列表）
  async function viewCollection(name: string) {
    setSelectedCollection(name);
    setSelectedDocument(null);
    setRawContent("");
    setActiveView("knowledge");
  }

  // 查看原始文档
  async function viewDocument(filename: string) {
    if (!selectedCollection) return;
    setSelectedDocument(filename);
    setContentLoading(true);
    try {
      const data = await getRawDocument(selectedCollection, filename);
      setRawContent(data.content);
    } catch (e) {
      message.error("加载文档失败");
    } finally {
      setContentLoading(false);
    }
  }

  // 拖拽移动文档到目标知识库
  async function handleDropOnCollection(targetCollection: string, e: React.DragEvent) {
    e.preventDefault();
    setDragOverTarget(null);
    const payload = e.dataTransfer.getData("application/json");
    if (!payload) return;
    try {
      const { filename, sourceCollection } = JSON.parse(payload);
      if (sourceCollection === targetCollection) return;
      const result = await moveDocument(sourceCollection, filename, targetCollection);
      message.success(result.message);
      // 刷新列表
      loadCollections();
      if (selectedCollection === sourceCollection) {
        setSelectedDocument(null);
        setRawContent("");
      }
    } catch (err) {
      message.error((err as Error).message);
    }
  }

  // 删除文档
  async function handleDelete(filename: string) {
    if (!selectedCollection) return;
    try {
      const result = await deleteDocument(selectedCollection, filename);
      message.success(result.message);
      loadCollections();
    } catch (err) {
      message.error((err as Error).message);
    }
  }

  // 新建知识库
  async function handleCreate() {
    const name = newName.trim();
    if (!name) { message.warning("请输入名称"); return; }
    try {
      const result = await createCollection(name, newIcon, newColor);
      message.success(result.message);
      setCreateModalOpen(false);
      setNewName("");
      setNewIcon("BookOutlined");
      setNewColor("#1677ff");
      loadCollections();
    } catch (err) {
      message.error((err as Error).message);
    }
  }

  // 重命名知识库
  async function handleRename(oldName: string) {
    const target = renameValue.trim();
    if (!target || target === oldName) { setRenaming(null); return; }
    try {
      const result = await renameCollection(oldName, target);
      message.success(result.message);
      setRenaming(null);
      setRenameValue("");
      if (selectedCollection === oldName) setSelectedCollection(target);
      loadCollections();
    } catch (err) {
      message.error((err as Error).message);
    }
  }

  // 删除知识库
  async function handleDeleteCollection(name: string) {
    try {
      const result = await deleteCollection(name);
      message.success(result.message);
      if (selectedCollection === name) {
        setSelectedCollection(null);
        setSelectedDocument(null);
        setRawContent("");
        setActiveView("chat");
      }
      loadCollections();
    } catch (err) {
      message.error((err as Error).message);
    }
  }

  // 上传配置
  const uploadProps = {
    fileList,
    multiple: true,
    showUploadList: false,
    accept: ".pdf,.md,.txt",
    beforeUpload: (file: File) => {
      const ext = file.name.toLowerCase().split(".").pop();
      if (!["pdf", "md", "txt"].includes(ext || "")) {
        message.error("只支持 PDF/MD/TXT 文件");
        return false;
      }
      return false; // 阻止自动上传
    },
    onChange: ({ fileList: newFileList }: { fileList: UploadFile[] }) => {
      setFileList(newFileList);
    },
  };

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#f0f2f5" }}>
      {/* 顶部标题栏 */}
      <div
        style={{
          background: "#fff",
          padding: "12px 24px",
          borderBottom: "1px solid #e8e8e8",
          display: "flex",
          alignItems: "center",
          gap: 12,
          boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
        }}
      >
        <DatabaseOutlined style={{ fontSize: 22, color: "#1677ff" }} />
        <div>
          <h1 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>个人知识库 Agent</h1>
          <p style={{ margin: 0, fontSize: 12, color: "#999" }}>基于你的笔记和文档回答，支持联网搜索与工具调用</p>
        </div>
      </div>

      {/* 主体内容区 */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* 左侧边栏 */}
        <div
          style={{
            width: 300,
            background: "#fff",
            borderRight: "1px solid #e8e8e8",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {/* 上传区域 */}
          <div style={{ padding: "10px 12px", borderBottom: "1px solid #f0f0f0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <UploadOutlined style={{ color: "#1677ff", fontSize: 13 }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: "#333" }}>上传资料</span>
              <span style={{ fontSize: 10, color: "#999", marginLeft: "auto" }}>自动归类</span>
            </div>
            <Upload {...uploadProps} disabled={fileList.length > 0 || uploading} style={{ display: "block" }}>
              <Button size="small" block icon={<UploadOutlined />} style={{ fontSize: 11, height: 28 }} disabled={fileList.length > 0 || uploading}>
                {fileList.length > 0 ? `已选 ${fileList.length} 个文件` : "点击选择文件"}
              </Button>
            </Upload>
            {fileList.length > 0 && (
              <>
                <Button
                  type="primary"
                  size="small"
                  block
                  style={{ marginTop: 4, height: 24, fontSize: 11 }}
                  onClick={handleUpload}
                  loading={uploading}
                >
                  {uploading ? "入库中…" : `上传 ${fileList.length} 个文件`}
                </Button>
                {uploading && (
                  <div style={{ marginTop: 4 }}>
                    <Progress
                      percent={uploadProgress.percent}
                      status="active"
                      size="small"
                      format={() => `${uploadProgress.current}/${uploadProgress.total}`}
                    />
                    <div style={{ fontSize: 10, color: "#999", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {uploadProgress.filename} {uploadProgress.percent}%
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* 知识库列表 */}
          <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: "#333", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <DatabaseOutlined style={{ color: "#1677ff" }} />
                知识库
              </span>
              <Tag color="blue" style={{ fontSize: 11 }}>{collections.length}</Tag>
              <Button
                type="text"
                size="small"
                icon={<PlusOutlined />}
                style={{ fontSize: 11, color: "#1677ff" }}
                onClick={() => setCreateModalOpen(true)}
              >
                新建
              </Button>
            </div>

            {collectionsLoading ? (
              <div style={{ textAlign: "center", padding: 20 }}>
                <Spin size="small" />
              </div>
            ) : collections.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无知识库" />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {collections.map((item) => (
                  <Card
                    key={item.name}
                    size="small"
                    hoverable
                    onClick={() => viewCollection(item.name)}
                    onDragOver={(e) => { e.preventDefault(); setDragOverTarget(item.name); }}
                    onDragLeave={() => setDragOverTarget(null)}
                    onDrop={(e) => handleDropOnCollection(item.name, e)}
                    style={{
                      cursor: "pointer",
                      border: dragOverTarget === item.name
                        ? "2px dashed #1677ff"
                        : selectedCollection === item.name
                          ? "1px solid #1677ff"
                          : "1px solid #f0f0f0",
                      background: dragOverTarget === item.name
                        ? "#e6f4ff"
                        : selectedCollection === item.name
                          ? "#e6f4ff"
                          : "#fff",
                      transition: "all 0.2s",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <Avatar
                        size="small"
                        icon={getCollectionIcon(item.icon)}
                        style={{ backgroundColor: item.color || "#1677ff", flexShrink: 0, cursor: "pointer" }}
                        onClick={(e) => {
                          e.stopPropagation();
                          const currentIdx = ICON_OPTIONS.findIndex((o) => o.key === item.icon);
                          const next = ICON_OPTIONS[(currentIdx + 1) % ICON_OPTIONS.length];
                          updateCollectionIcon(item.name, next.key).then(() => loadCollections());
                        }}
                        title="点击切换图标"
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        {renaming === item.name ? (
                          <Input
                            size="small"
                            value={renameValue}
                            onChange={(e) => setRenameValue(e.target.value)}
                            onPressEnter={() => handleRename(item.name)}
                            onBlur={() => handleRename(item.name)}
                            autoFocus
                            style={{ fontSize: 13 }}
                            onClick={(e) => e.stopPropagation()}
                          />
                        ) : (
                          <div style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {item.name}
                          </div>
                        )}
                        <div style={{ fontSize: 11, color: "#999", marginTop: 2 }}>
                          {item.documents.length} 个文档
                        </div>
                      </div>
                      {renaming !== item.name && (
                        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                          <EditOutlined
                            style={{ fontSize: 14, color: "#999", cursor: "pointer" }}
                            onClick={(e) => {
                              e.stopPropagation();
                              setRenaming(item.name);
                              setRenameValue(item.name);
                            }}
                          />
                          <Popconfirm
                            title="确认删除该知识库？"
                            description={`将移除「${item.name}」及其所有文档`}
                            onConfirm={(e) => { e?.stopPropagation(); handleDeleteCollection(item.name); }}
                            onCancel={(e) => e?.stopPropagation()}
                            okText="删除"
                            cancelText="取消"
                            okButtonProps={{ danger: true }}
                          >
                            <DeleteOutlined
                              style={{ fontSize: 14, color: "#ff4d4f", cursor: "pointer" }}
                              onClick={(e) => e.stopPropagation()}
                            />
                          </Popconfirm>
                        </div>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>

          {/* 底部导航 */}
          <div style={{ padding: 12, borderTop: "1px solid #f0f0f0", display: "flex", gap: 8 }}>
            <Button
              block
              type={activeView === "chat" ? "primary" : "default"}
              icon={<MessageOutlined />}
              onClick={() => setActiveView("chat")}
            >
              对话
            </Button>
            <Button
              block
              type={activeView === "knowledge" ? "primary" : "default"}
              icon={<DatabaseOutlined />}
              onClick={() => setActiveView("knowledge")}
            >
              知识库
            </Button>
          </div>
        </div>

        {/* 右侧内容区 */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {activeView === "chat" ? (
            <>
              {/* 对话区域 */}
              <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
                {messages.length === 0 && !loading && (
                  <Empty description="开始对话吧" style={{ padding: "60px 0" }}>
                    <p style={{ color: "#999", fontSize: 13 }}>
                      试试问："Python 装饰器是什么" 或 "今天天气怎么样"
                    </p>
                  </Empty>
                )}

                <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 800, margin: "0 auto" }}>
                  {messages.map((m, i) => (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                      }}
                    >
                      <div
                        style={{
                          maxWidth: "70%",
                          padding: "12px 16px",
                          borderRadius: m.role === "user" ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
                          backgroundColor: m.role === "user" ? "#1677ff" : "#f5f5f5",
                          color: m.role === "user" ? "#fff" : "#333",
                          lineHeight: 1.6,
                        }}
                      >
                        <div style={{ fontSize: 12, marginBottom: 4, opacity: 0.7 }}>
                          {m.role === "user" ? "你" : "Agent"}
                        </div>
                        <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
                      </div>
                    </div>
                  ))}
                  {loading && (
                    <div style={{ display: "flex", justifyContent: "flex-start" }}>
                      <div
                        style={{
                          padding: "12px 16px",
                          borderRadius: "18px 18px 18px 4px",
                          backgroundColor: "#f5f5f5",
                        }}
                      >
                        <Spin size="small" />
                        <span style={{ marginLeft: 8, color: "#999" }}>思考中…</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* 输入区域 */}
              <div style={{ padding: 16, background: "#fff", borderTop: "1px solid #e8e8e8" }}>
                <div style={{ display: "flex", gap: 8, maxWidth: 800, margin: "0 auto" }}>
                  <TextArea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        send();
                      }
                    }}
                    placeholder="向你的知识库提问（Enter 发送，Shift+Enter 换行）"
                    autoSize={{ minRows: 1, maxRows: 4 }}
                    style={{ flex: 1 }}
                  />
                  <Button
                    type="primary"
                    icon={<SendOutlined />}
                    onClick={send}
                    loading={loading}
                    disabled={!input.trim()}
                    size="large"
                  >
                    发送
                  </Button>
                </div>
              </div>
            </>
          ) : (
            /* 知识库详情区域 */
            <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
              {!selectedCollection ? (
                <Empty description="请从左侧选择一个知识库" style={{ padding: "60px 0" }} />
              ) : !selectedDocument ? (
                /* 文档列表 */
                <div style={{ maxWidth: 900, margin: "0 auto" }}>
                  <div style={{ marginBottom: 24 }}>
                    <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 8 }}>
                      <FolderOutlined style={{ marginRight: 8, color: "#1677ff" }} />
                      {selectedCollection}
                    </h2>
                    <p style={{ color: "#666", fontSize: 13, margin: 0 }}>
                      共 {collections.find((c) => c.name === selectedCollection)?.documents.length || 0} 个文档
                    </p>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
                    {collections
                      .find((c) => c.name === selectedCollection)
                      ?.documents.map((doc) => (
                        <Card
                          key={doc}
                          hoverable
                          onClick={() => viewDocument(doc)}
                          draggable
                          onDragStart={(e) => {
                            e.dataTransfer.setData("application/json", JSON.stringify({
                              filename: doc,
                              sourceCollection: selectedCollection,
                            }));
                            e.dataTransfer.effectAllowed = "move";
                          }}
                          style={{ cursor: "grab" }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                            <div style={{ fontSize: 32 }}>{getFileIcon(doc)}</div>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontSize: 14, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                {doc}
                              </div>
                              <div style={{ fontSize: 12, color: "#999", marginTop: 4 }}>
                                点击查看原文
                              </div>
                            </div>
                            <Popconfirm
                              title="确认删除？"
                              description={`将从「${selectedCollection}」中移除 ${doc}`}
                              onConfirm={(e) => { e?.stopPropagation(); handleDelete(doc); }}
                              onCancel={(e) => e?.stopPropagation()}
                              okText="删除"
                              cancelText="取消"
                              okButtonProps={{ danger: true }}
                            >
                              <Button
                                type="text"
                                size="small"
                                danger
                                icon={<DeleteOutlined />}
                                onClick={(e) => e.stopPropagation()}
                              />
                            </Popconfirm>
                          </div>
                        </Card>
                      ))}
                  </div>
                </div>
              ) : (
                /* 文档内容 */
                <div style={{ maxWidth: 900, margin: "0 auto" }}>
                  <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 12 }}>
                    <Button
                      size="small"
                      onClick={() => setSelectedDocument(null)}
                    >
                      ← 返回文档列表
                    </Button>
                    <Divider type="vertical" />
                    <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
                      {getFileIcon(selectedDocument)}
                      <span style={{ marginLeft: 8 }}>{selectedDocument}</span>
                    </h3>
                  </div>

                  <Card>
                    {contentLoading ? (
                      <div style={{ textAlign: "center", padding: 40 }}>
                        <Spin />
                      </div>
                    ) : (
                      <div
                        style={{
                          whiteSpace: "pre-wrap",
                          lineHeight: 1.8,
                          fontSize: 14,
                          color: "#333",
                          fontFamily: "monospace",
                          background: "#fafafa",
                          padding: 16,
                          borderRadius: 6,
                          maxHeight: "calc(100vh - 200px)",
                          overflow: "auto",
                        }}
                      >
                        {rawContent}
                      </div>
                    )}
                  </Card>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 新建知识库弹窗 */}
      <Modal
        title="新建知识库"
        open={createModalOpen}
        onOk={handleCreate}
        onCancel={() => { setCreateModalOpen(false); setNewName(""); setNewIcon("BookOutlined"); setNewColor("#1677ff"); }}
        okText="创建"
        cancelText="取消"
      >
        <Input
          placeholder="输入知识库名称"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onPressEnter={handleCreate}
          autoFocus
          style={{ marginBottom: 16 }}
        />
        <div style={{ fontSize: 12, color: "#666", marginBottom: 8 }}>选择图标：</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, maxHeight: 140, overflow: "auto" }}>
          {ICON_OPTIONS.map((opt) => (
            <div
              key={opt.key}
              onClick={() => setNewIcon(opt.key)}
              style={{
                width: 32,
                height: 32,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 16,
                border: newIcon === opt.key ? `2px solid ${newColor}` : "1px solid #e8e8e8",
                background: newIcon === opt.key ? `${newColor}15` : "#fff",
                transition: "all 0.2s",
              }}
            >
              {opt.icon}
            </div>
          ))}
        </div>
        <div style={{ fontSize: 12, color: "#666", margin: "12px 0 8px" }}>选择颜色：</div>
        <div style={{ display: "flex", gap: 8 }}>
          {COLOR_OPTIONS.map((c) => (
            <div
              key={c}
              onClick={() => setNewColor(c)}
              style={{
                width: 24,
                height: 24,
                borderRadius: "50%",
                background: c,
                cursor: "pointer",
                border: newColor === c ? "3px solid #333" : "2px solid transparent",
                transition: "all 0.2s",
              }}
            />
          ))}
        </div>
        <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, color: "#999" }}>预览：</span>
          <Avatar size="default" icon={getCollectionIcon(newIcon)} style={{ backgroundColor: newColor }} />
        </div>
      </Modal>
    </div>
  );
}
