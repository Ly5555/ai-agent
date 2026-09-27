# AI Knowledge Agent

> 一个基于 RAG + LangGraph 的智能问答 Agent 项目（面试作品集）。

## 项目简介

- **一句话定位**：（TODO：用一句话说明这个 Agent 能帮用户做什么，例如“基于私有知识库的 RAG 问答 Agent”）
- **目标用户**：（TODO）
- **核心亮点**：（TODO：RAG 检索、多步推理、工具调用、流式输出……列 2-3 个）

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | FastAPI + LangGraph + (LLM 网关) |
| 检索 | RAG（向量库 + 召回 + 重排） |
| 前端 | React + Vite + TypeScript |
| 部署 | Docker Compose 一键启动 |

## 目录结构

```
ai-knowledge-agent/
├── README.md            # 项目说明（本文件）
├── docker-compose.yml   # 一键启动所有服务
├── backend/             # 后端
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py      # FastAPI 入口
│   │   ├── agents/      # LangGraph Agent 逻辑
│   │   ├── rag/         # RAG 检索逻辑
│   │   └── tools/       # 工具函数
├── frontend/            # 前端
│   ├── package.json
│   ├── src/
│   │   ├── components/  # React 组件
│   │   ├── hooks/       # 自定义 Hooks
│   │   └── services/    # API 调用封装
└── docs/                # 架构图、接口文档
```

## 快速开始

```bash
# 一键启动（后端 + 前端 + 依赖服务）
docker compose up --build

# 或本地分模块启动
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

## 架构图

> 见 `docs/` 目录（TODO：放一张架构图，面试加分项）。

## API 文档

> 见 `docs/` 目录（TODO：接口说明 / OpenAPI 截图）。

## 待完成

- [ ] Agent 主流程（LangGraph 图定义）
- [ ] RAG 召回与重排
- [ ] 工具注册与调用
- [ ] 前端对话界面
- [ ] 架构图与接口文档
