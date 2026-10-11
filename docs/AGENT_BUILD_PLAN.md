# 个人知识库 Agent —— 会查资料、会反省、会干活的文档问答 Agent（21 天基础 + 多 Agent 对比）

> 项目定位（面试主标题）：**个人知识库 Agent**——一个会查资料、会反省、会干活的文档问答 Agent。
> 三大能力映射：
> - **会查资料** = RAG 检索（按知识分类整理，分类检索是差异化特性）
> - **会反省** = ①回答前反省(Grounding：生成后逐句校验依据，无依据则删/降级) ②干活后反省(工具结果校验，不对重试/换工具) ③检索后反省(Self-RAG：召回不够改写 query 重查，D9 核心)
> - **会干活** = 基础三件套（calculator / 当前时间 / web_search）
> 差异化卖点：个人知识分类 + 自动沉淀 FAQ（生产侧 Agent）。
>
> 使用规则：每天一个 git commit；达到"✅ 完成标准"就走人，别过度打磨；
> 卡住 2 小时就去搜/问，卡住半天就砍掉当天功能的可选项（主链路永远优先）。

---

## 第一周：把"知识库"做实（RAG 基础链路）

### D1｜选型 + 环境准备
- [x] 安装依赖：`chromadb`、`pypdf`、`langchain-community`（分块器）——已装入 backend/.venv（chromadb 1.5.9 / pypdf 6.20.0 / langchain-community 0.4.2）
- [x] 确定 embedding 方案：**GLM embedding-3**（2048 维，与 GLM-4-flash 同网关同 Key；OpenAI 兼容 /embeddings 接口）
- [x] 建目录：`data/docs/Python学习笔记/`、`data/docs/前端学习笔记/`（各含 .gitkeep 占位）

**✅ 完成标准**：写个小脚本，调通一次 embedding 接口，拿到向量。（✔️ D1 完成：`backend/embeddings.py` 的自检入口已实测 2048 维、非零向量）

### D2｜文档入库脚本（核心）
- [x] 新建 `backend/vector_store.py`：
  - 加载 PDF / Markdown → `RecursiveCharacterTextSplitter` 分块（实测：chunk 600 字、overlap 100，中文标点分隔符）
  - 写入 ChromaDB，**每个分块带 metadata：`collection` / `source` / `page`**（已实测可过滤）
- [x] 准备《Python学习笔记.md》和《React学习笔记.md》作为测试素材

**✅ 完成标准**：命令行跑一次脚本，Chroma 里能查到分块数和 metadata。

### D3｜上传接口
- [ ] 在 `backend/main.py` 新增 `POST /api/upload`（FastAPI `UploadFile`），接收文件 + `collection` 参数
- [ ] 文件落盘到 `data/docs/<知识分类>/`，调用 D2 的 ingest
- [ ] 在 `backend/agent.py` 或独立模型文件中补齐对应响应模型

**✅ 完成标准**：curl 或 /docs 页面上传一个 PDF，返回"入库 N 块"。

### D4｜检索服务
- [ ] 在 `backend/vector_store.py` 的 `query()` 基础上补齐检索服务：
  - 输入 query + collection → ChromaDB 相似度检索 top-k
  - **强制带 metadata 过滤** → 返回块列表（含来源信息）
- [ ] （可选，有余力再做）BM25 混合召回（`rank_bm25`）

**✅ 完成标准**：脚本验证——问 Python 笔记的问题只会召回 Python 分类的块。

### D5｜retrieve / generate 换成真的（关键一天）
- [ ] `backend/agent.py`：`retrieve` 节点调 D4，检索结果写入 state（如 `context: list[dict]`）
- [ ] `generate` 节点重写 prompt：系统指令 + 检索上下文 + **history 真正拼进 prompt**（多轮对话从今天起由假变真）+ 用户问题

**✅ 完成标准**：前端 `/chat` 问笔记里的内容，能得到基于知识库的回答。

### D6｜来源引用 + 修复日
- [ ] generate 回答末尾列出引用来源（格式："根据《Python学习笔记》第 3 节…"，由 LLM 基于上下文标注）
- [ ] 修 D2~D5 积累的小 bug
- [ ] 把 `backend/agent.py` 里"异常就 mock"的兜底改成**先记日志再兜底**（避免 bug 被静默吞掉）

**✅ 完成标准**：10 个自测问题里 ≥7 个回答带正确来源；多轮指代（"它呢？"）能接上。

### D7｜缓冲 / 休息
- [ ] 补前面落后的进度，或更新 README 功能清单

> 里程碑：到此你已拥有"能用的 RAG 问答系统"。

---

## 第二周：把"Agent"做出来（决策、循环、工具）

### D8｜grade 节点（自我评估）
- [ ] 新节点 `grade`：用小 prompt 让 LLM 判断"检索到的内容能否支撑回答问题"
  - 输出结构化结果（Pydantic OutputParser，或强制输出 `relevant` / `irrelevant`）
- [ ] state 加 `retry_count` 字段

**✅ 完成标准**：单独脚本测试 grade 对"相关 / 不相关上下文"判断准确。

### D9｜rewrite 节点 + 循环图（本周最重要 + 检索后反省）
- [ ] 新节点 `rewrite`：LLM 把原 query 换个说法
- [ ] 图改成条件边（LangGraph `add_conditional_edges`，本项目灵魂 API，认真读文档）：

```
retrieve → grade →(够)→ generate
                 →(不够且 retry<2)→ rewrite → retrieve（循环）
                 →(不够且用完)→ fallback
```

**✅ 完成标准**：故意问一个笔记里没有、但换个关键词能命中的问题，
日志里能看到"检索→判否→改写→重查→回答"的完整轨迹。**这一刻项目才配叫 Agent。**
> 注：这步是"**检索后反省 / Self-RAG**"——召回不够就改写 query 重查，是三种反省机制之③；①②③ 全部必做（①回答前 Grounding 在 D12，②干活后反省在 D11，③检索后反省即本日 D9）。

### D10｜router 入口分流
- [ ] 图入口加 `router` 节点：LLM 分类问题 → `知识库问题` / `闲聊直答` / `需要外部信息`

**✅ 完成标准**：问"你好"不触发检索；问手册内容走 RAG；问"今天天气"被识别为需要工具。

### D11｜工具节点 + 干活后反省
- [ ] 定义 **基础三件套** 工具：`calculator` + `current_time`（当前时间）+ `web_search`（免费 `duckduckgo-search`）
- [ ] 加工具节点，把工具结果并入 generate
- [ ] **干活后反省（锁定的反省机制②）**：工具返回后加一步"结果校验"——结果明显错误 / 为空 / 格式不对 → 重试该工具，或换工具，绝不拿错误结果编进答案

**✅ 完成标准**：问实时天气 / 现在几点，Agent 自己调工具回答；故意给非法输入（如让 calculator 算错表达式），看它重试 / 换工具而不是瞎编。

### D12｜回答前反省（Grounding 逐句校验）+ 知识缺口记录
- [ ] 重试耗尽仍无结果 → 回答"知识库中暂无相关信息"（prompt 里严禁编造）
- [ ] **真正的 Grounding 校验（锁定的反省①）**：generate 产出答案后，多一次轻量 LLM call，让模型逐句标注"该句是否有检索上下文依据"；无依据的句子直接删除，或降级为"这一点我不太确定"——面试被问"你的 Grounding 校验什么"时能答出这句
- [ ] 同时把该 query 写入 `data/gaps.jsonl`（知识分类、问题、时间）——知识缺口的数据源

**✅ 完成标准**：刁钻问题得到诚实回答；回答里不出现"凭空冒出来"的句子（逐句依据可解释）；gaps 文件里新增一条记录。

### D13｜集成测试日（不写新功能）
- [ ] 自己出 20 道题：10 道库里有答案、5 道没有、3 道闲聊、2 道要工具
- [ ] 跑通并记录表现，修最差的几个 case

**✅ 完成标准**：20 道里明显错误 ≤3，且没有一道是"编造答案"。

---

## 第三周：沉淀 Agent + 前端亮点 + 面试包装

### D14｜沉淀 Agent 图（新文件 `agents/curator.py`）
- [ ] 输入：一批答疑记录（先手写一份假的 `faq_raw.md` 模拟群聊问答）
- [ ] 流程：LLM 聚类高频问题 → 每个问题生成一条规范 FAQ 草稿（问题 + 标准答案 + 所属知识分类）

**✅ 完成标准**：20 条乱糟糟的答疑 → 自动归纳成 5~8 条 FAQ 草稿。

### D15｜FAQ 入库闭环（项目名字级卖点，今天就绪）
- [ ] 草稿复用 D2 的 ingest 写入向量库（metadata `type=faq`）
- [ ] 新增 `POST /api/curate` 手动触发沉淀

**✅ 完成标准**：跑一次沉淀 → 立刻问该 FAQ 覆盖的问题 → 能答上。
> 至此"消费问答 + 生产知识"闭环完成。

### D16｜后端流式输出
- [ ] 用 `graph.astream_events()`，新增 `/api/chat/stream`（FastAPI `StreamingResponse` 或 `sse-starlette`）
- [ ] 逐 token 推送，并把节点事件（retrieve / grade / … 开始执行）一并推给前端

**✅ 完成标准**：curl 能看到 SSE 数据流。

### D17｜前端打字机
- [ ] `ChatView.tsx` + `services/api.ts` 接 SSE（`EventSource` 或 fetch reader），逐字渲染

**✅ 完成标准**：回答像打字机一样输出。

### D18｜CanvasView 接真实执行链路（差异化王牌）
- [ ] 替换现在画布上 3 个写死的假节点，改为真实图结构（router / retrieve / grade / rewrite / tool / generate）
- [ ] 把 D16 推来的节点事件映射到 ReactFlow：**当前执行到哪个节点哪个就高亮**，循环重试时能肉眼看见轨迹回到 rewrite

**✅ 完成标准**：演示 D9 的"改写重试"case 时，画布上能看见轨迹转了两圈。
> 面试现场演这个，比任何 PPT 都有说服力。

### D19｜知识缺口看板
- [ ] 新接口 `GET /api/gaps` + 简单页面：列出"被反复问但库里没有"的问题
- [ ] （可选）加"按缺口生成待整理任务"按钮 → 调 D14 的沉淀 Agent

**✅ 完成标准**：能看到 D12 记录的缺口列表。

### D20｜多分类资料演示剧本
- [ ] 准备 Python、前端各一份学习笔记与一份答疑记录，内容主题明确区分
- [ ] 写好演示 5 连问：
  1. 单分类问题
  2. 跨分类对比问题
  3. 库里没有的问题（触发重试 + 诚实兜底）
  4. 天气问题（触发工具）
  5. 沉淀 FAQ 之后再问同一个问题
- [ ] 从头到尾录一遍屏

**✅ 完成标准**：5 连问演示全程录屏，无翻车。

### D21｜评测 + 文档收尾
- [ ] 写 `eval.py`：20 道题跑批，统计召回命中率 / 拒答正确率，拿到**可以说出数字的指标**
- [ ] README 填满 TODO：架构图（drawio 画真实的循环图）、接口文档、演示 GIF
- [ ] 准备面试话术：
  - 为什么用 LangGraph？→ 条件边和循环（固定链路做不到自我修正）
  - 怎么防幻觉？→ grade 重试 + 无结果明确拒答 + 来源引用
  - 为什么按知识分类整理？→ metadata 过滤，新增分类零成本
  - 生产落地考虑？→ 数据脱敏 / 私有化模型网关 / 缺口看板驱动知识运营
  - 为什么 / 何时用多 Agent？→ 单 Agent 够简单场景；子能力需独立演进 / 隔离上下文 / 并行时才拆 Supervisor，代价是延迟与调试难
  - 三种架构怎么选？→ ReAct 简单提示驱动 / 图编排固定可控 / 多 Agent 子能力隔离并行，按场景取舍

---

## 第四周（可选封顶项，做不完不可惜）：单 Agent 图编排 ↔ 多 Agent Supervisor 对比

> ⚠️ 可选封顶：前三周 21 天做完已是完整作品。第四周纯加分，做不完绝不影响交付。
> 目标岗位是 Agent/框架工程师，必须能讲清"为什么 / 何时用多 Agent"。下面按 2~3 天估算（多 Agent 拆分 + 状态传递是 LangGraph 坑最密处，别一天硬塞）。

### D22｜拆子 Agent + Supervisor 分发（核心重构，最坑）
- [ ] 把 D5/D9/D11 的"查资料 / 反省 / 干活"三个能力拆成**三个子 Agent**
- [ ] 加 `Supervisor` 节点（router）：LLM 判断问题类型 → 分发给对应子 Agent → 结果交回 Supervisor 汇总
- [ ] 重点踩坑：子 Agent 间状态怎么传（共用 ChatState 还是各自 State）、上下文怎么不丢

**✅ 完成标准**：混合问题能被 Supervisor 正确分发到子 Agent 并汇总出答案。

### D23｜跑双版评测 + 写对比结论
- [ ] 复用 D21 的 `eval.py` 评测集，分别跑 **单 Agent 图编排（你前三周做的固定节点+条件边）** 与 **多 Agent Supervisor** 两版
- [ ] 记录并对比：回答质量 / 端到端延迟 / 可维护性 / 上下文丢失风险

**✅ 完成标准**：写出对比结论——多 Agent 在 X 类问题更好，但代价是 Y（延迟 / 调试难 / 上下文割裂）；能说清"何时该用、何时不该用"。

### D24（锦上添花，可选）｜朴素 ReAct 版凑齐三形态
- [ ] 另做一个最朴素的 ReAct 循环版（thought→act→observe 纯提示驱动，无图编排），与上面两版并排
- [ ] 三形态对比：ReAct vs 图编排 vs 多 Agent，分别对应"简单 / 中等 / 复杂"场景的取舍

**✅ 完成标准**：面试能一句话讲清三种架构各自适合什么场景。

## 面试讲述结构（两档，别一次性倒完）

**15 秒电梯版（开场用）：**
> "我做了「个人知识库 Agent」：会查资料、会反省、会干活的文档问答 Agent，前端还能实时看到 Agent 的推理轨迹。"

**2 分钟展开版（被追问再上）：**
> "会查资料（RAG，按知识分类整理）、会反省（回答前逐句 Grounding 校验 + 干活后工具结果校验 + 检索不够自动改写重查）、会干活（calculator / 时间 / 搜索工具）。
> 个人学习笔记和项目资料自动沉淀成知识库；查不到就明确说不知道并记录成知识缺口，绝不编造。
> 前端画布实时可视化 LangGraph 执行轨迹（含重试循环）。
> 我还对比了单 Agent 图编排与多 Agent Supervisor 两种架构，结论是……（何时该用多 Agent）。"

## 后续可做（D22 之后，别提前碰）

- 会话记忆持久化（LangGraph checkpointer / SQLite）
- 人工审核 FAQ 草稿的流程
- 重排模型（bge-reranker）提升召回质量
- 定时任务调度沉淀 Agent（cron / APScheduler）
