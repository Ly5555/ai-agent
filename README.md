# 个人知识库 Agent

> 基于 RAG + LangGraph 的个人文档问答 Agent。上传学习笔记和项目资料后，可以检索、问答，并逐步支持总结、练习题与来源引用。

## 项目简介

- **一句话定位**：一个基于个人文档的 RAG 知识助手。
- **目标用户**：需要整理学习笔记、技术文档和项目资料的个人开发者。
- **核心亮点**：文档上传、按知识分类检索、基于资料回答与来源引用。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | FastAPI + LangGraph + Pydantic |
| 检索 | RAG（向量库 + 召回 + 重排，TODO） |
| 前端 | React + Vite + TypeScript + ReactFlow + React Router |
| 部署 | Docker Compose 一键启动 |

## 目录结构

```
ai-knowledge-agent/
├── README.md            # 项目说明（本文件）
├── docker-compose.yml   # 一键启动（前端代理自动转发 /api 到后端）
├── backend/             # 后端
│   ├── main.py          # FastAPI 入口（/api/chat、/api/upload、/api/health）
│   ├── agent.py         # LangGraph 对话图与请求/响应模型
│   ├── vector_store.py  # ChromaDB 入库与检索
│   ├── document_loader.py # PDF / Markdown / TXT 加载
│   ├── chunker.py       # 中文文本分块
│   ├── embeddings.py    # GLM embedding-3 向量化
│   ├── config.py        # 模型网关与 CORS 配置
│   └── requirements.txt
├── data/                # 项目数据（挂载给 Docker 后端）
│   ├── docs/            # 文档，按知识分类目录整理
│   └── chroma/          # 本地向量库（Git 忽略）
├── frontend/            # 前端
│   ├── package.json
│   ├── index.html
│   ├── vite.config.ts   # 开发代理：/api、/health → 后端 8000
│   └── src/
│       ├── main.tsx     # 入口
│       ├── App.tsx      # 根组件（RouterProvider）
│       ├── views/       # 页面组件（CanvasView 画布 / ChatView 聊天）
│       ├── services/    # API 调用封装（api.ts）
│       ├── types/       # TypeScript 类型定义
│       └── router/      # 路由配置
└── docs/                # 架构图、接口文档
```

## 快速开始

```bash
# 1) 后端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload            # http://localhost:8000/docs

# 2) 前端（另开一个终端）
cd frontend
npm install
npm run dev                          # http://localhost:5173

# 或一键启动（含 Docker）
docker compose up --build
```

## 前后端如何连通

- 开发期：前端 `vite.config.ts` 已配代理，`/api`、`/health` 自动转发到后端 `8000`，
  因此 `services/api.ts` 用相对路径即可，无需处理跨域。
- 后端也开了 CORS（`config.py` 的 `cors_origins`），直接用 `http://localhost:8000` 调也行。
- Docker 下前端通过环境变量 `VITE_BACKEND_PROXY_TARGET=http://backend:8000` 指向容器内的后端服务。

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| POST | `/api/chat` | 对话（body: `{query, history}`） |
| POST | `/api/upload` | 上传 PDF、Markdown 或 TXT（form-data: `file`、`collection`） |

> 未配置 `LLM_API_KEY` 时，`/api/chat` 返回 mock 回答，保证本地能跑通；
> 配上 GLM-4-flash / OpenAI 网关后自动走真实 LLM。

## 待完成

> 📅 详细施工计划见 [docs/AGENT_BUILD_PLAN.md](docs/AGENT_BUILD_PLAN.md)（21 天，每天一个可验收目标）

- [ ] RAG 召回与重排（backend/agent.py 的 retrieve 节点）
- [ ] 工具节点 + 条件分支
- [ ] 前端聊天界面联调真实 LLM
- [ ] 架构图与接口文档（docs/）
