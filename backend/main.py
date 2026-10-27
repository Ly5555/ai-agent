"""FastAPI 入口：聊天接口 + 健康检查 + 文件上传入库。

扁平化后运行方式：
    cd backend && uvicorn main:app --reload --port 8000
"""
import logging
import json
import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent import ChatRequest, ChatResponse, export_graph, run_agent
from config import settings
from vector_store import DOCS_DIR, get_collection, ingest_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger("ai-knowledge-agent")

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXT = {".pdf", ".md", ".txt"}


class UploadResponse(BaseModel):
    message: str
    collection: str
    filename: str
    chunks: int


def validate_collection_name(value: str) -> str:
    """只允许单层知识分类名，避免上传路径越界。"""
    name = value.strip()
    if not name or name in {".", ".."} or Path(name).name != name or "\\" in name:
        raise HTTPException(status_code=400, detail="知识分类名称不合法")
    return name


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "message": "FastAPI 后端服务启动成功！"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    return run_agent(req)


@app.get("/api/graph")
def graph() -> dict:
    """导出真实 LangGraph 拓扑（带坐标），供前端画布渲染。"""
    return export_graph()


@app.post("/api/curate")
def curate() -> dict:
    """D15：触发沉淀 Agent 生成 FAQ 草稿，并把有答案的 FAQ 灌回向量库，闭环完成。

    流程：run_curator()（读 gaps.jsonl → 聚类 → 复用问答图取答案 → 写 faq_draft.md）
        → parse_faq_draft()（解析草稿，跳过「待补充」）
        → ingest_faq()（每条 FAQ 作为 type=faq 块入库，按所属知识分类路由）
    """
    from curator import DRAFT_FILE, parse_faq_draft, run_curator
    from vector_store import ingest_faq

    stat = run_curator()
    faqs = parse_faq_draft(DRAFT_FILE)
    ingested = 0
    skipped = 0
    for f in faqs:
        coll = f["collection"]
        if not coll:
            logger.warning("curate 跳过无分类 FAQ：%r", f["question"])
            skipped += 1
            continue
        ingested += ingest_faq(f["question"], f["answer"], coll)
    logger.info(
        "curate 完成：草稿 %d 条 → 入库 %d 块，跳过无分类 %d 条",
        len(faqs), ingested, skipped,
    )
    return {
        "gaps": stat.get("gaps", 0),
        "clusters": stat.get("clusters", 0),
        "faq_parsed": len(faqs),
        "faq_ingested": ingested,
        "faq_skipped": skipped,
        "draft_path": stat.get("draft_path", ""),
    }


def _get_existing_collections() -> list[str]:
    """获取已有知识库分类名列表。"""
    try:
        collection = get_collection()
        data = collection.get(include=["metadatas"])
        metadatas = data.get("metadatas", [])
        names = set()
        for meta in metadatas:
            coll = meta.get("collection", "")
            if coll:
                names.add(coll)
        return sorted(names)
    except Exception:
        return []


def _auto_classify(text_preview: str, filename: str, existing: list[str]) -> str:
    """用 LLM 根据文件内容自动判断归属分类。"""
    from langchain_openai import ChatOpenAI
    from config import make_http_client

    existing_str = "、".join(existing) if existing else "（暂无）"
    prompt = (
        f"你是一个文档分类助手。已有知识库分类：{existing_str}。\n"
        f"文件名：{filename}\n"
        f"文件内容前 500 字：\n{text_preview}\n\n"
        "请根据内容判断该文件应归入哪个已有分类。"
        "如果没有任何已有分类合适，则新建一个简短的中文分类名（2-6个字）。\n"
        "只输出分类名，不要解释。"
    )
    try:
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0,
            http_client=make_http_client(),
        )
        result = llm.invoke(prompt).content.strip()
        # 清理可能的引号
        result = result.strip("\"'""''")
        if result and len(result) <= 20:
            return result
    except Exception as e:
        logger.warning("自动分类失败，使用默认分类：%s", e)
    return "未分类"


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """D16：SSE 流式问答。事件流格式见 agent.stream_agent 的 yield 字典。

    用 FastAPI 自带 StreamingResponse（text/event-stream），不引第三方 sse 库。
    """
    from agent import stream_agent

    async def event_gen():
        async for ev in stream_agent(req):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.post("/api/upload", response_model=UploadResponse)
def upload(file: UploadFile = File(...), collection: str = Form("")) -> UploadResponse:
    """保存一份原文档并入库。collection 留空时由 LLM 自动识别分类。"""
    filename = Path(file.filename or "").name
    ext = Path(filename).suffix.lower()
    logger.info("收到上传请求：collection=%s filename=%s ext=%s", collection, filename, ext)
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型 {ext}，仅支持 pdf/md/txt")
    if not filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # 自动分类：collection 为空时读取内容让 LLM 判断
    if not collection.strip():
        # 先保存到临时位置读取内容
        tmp_dir = DOCS_DIR / "_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / filename
        with tmp_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)
            file.file.seek(0)

        # 提取文本预览
        try:
            if ext == ".pdf":
                from document_loader import load_file as dl_load
                docs = dl_load(tmp_path, "_tmp", filename)
                text_preview = "\n".join(d.get("text", "") for d in docs)[:500]
            else:
                text_preview = tmp_path.read_text(encoding="utf-8", errors="ignore")[:500]
        except Exception:
            text_preview = filename  # 降级：只用文件名判断

        existing = _get_existing_collections()
        collection = _auto_classify(text_preview, filename, existing)
        tmp_path.unlink(missing_ok=True)
        logger.info("自动分类结果：%s -> %s", filename, collection)

    collection_name = validate_collection_name(collection)
    target_dir = DOCS_DIR / collection_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    with target.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    logger.info("原文档已保存：%s", target)

    try:
        count = ingest_file(target, collection_name, source_name=filename)
    except ValueError as e:
        logger.warning("入库被拒（可预期错误）：%s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("入库失败（意外错误）：%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"入库失败：{e}")
    return UploadResponse(
        message=f"已归入「{collection_name}」，入库 {count} 块",
        collection=collection_name,
        filename=filename,
        chunks=count,
    )


class MoveRequest(BaseModel):
    source_collection: str
    filename: str
    target_collection: str


@app.post("/api/documents/move")
def move_document(req: MoveRequest) -> dict:
    """将文档从一个知识库分类移动到另一个。"""
    src = validate_collection_name(req.source_collection)
    dst = validate_collection_name(req.target_collection)
    filename = Path(req.filename).name

    if src == dst:
        raise HTTPException(status_code=400, detail="源和目标分类相同")

    src_path = DOCS_DIR / src / filename
    if not src_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在：{src}/{filename}")

    # 1. 从向量库删除旧分类下的 chunks
    vector_collection = get_collection()
    vector_collection.delete(
        where={"$and": [{"collection": src}, {"source": filename}]}
    )
    logger.info("已删除旧 chunks：%s/%s", src, filename)

    # 2. 移动物理文件
    dst_dir = DOCS_DIR / dst
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_path = dst_dir / filename
    shutil.move(str(src_path), str(dst_path))
    logger.info("文件已移动：%s/%s -> %s/%s", src, filename, dst, filename)

    # 3. 重新入库到新分类
    try:
        count = ingest_file(dst_path, dst, source_name=filename)
    except Exception as e:
        logger.error("重新入库失败：%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"入库失败：{e}")

    return {"message": f"已将「{filename}」从「{src}」移到「{dst}」", "chunks": count}


class DeleteRequest(BaseModel):
    collection: str
    filename: str


@app.post("/api/documents/delete")
def delete_document(req: DeleteRequest) -> dict:
    """删除一个文档：从向量库移除 chunks 并删除物理文件。"""
    coll = validate_collection_name(req.collection)
    filename = Path(req.filename).name

    file_path = DOCS_DIR / coll / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在：{coll}/{filename}")

    # 1. 从向量库删除
    vector_collection = get_collection()
    vector_collection.delete(
        where={"$and": [{"collection": coll}, {"source": filename}]}
    )

    # 2. 删除物理文件
    file_path.unlink()
    logger.info("已删除文档：%s/%s", coll, filename)

    return {"message": f"已删除「{filename}」"}


import json


def _read_collection_meta(dir_path: Path) -> dict:
    """读取分类目录下的 .meta.json，不存在则返回默认值。"""
    meta_file = dir_path / ".meta.json"
    if meta_file.exists():
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _write_collection_meta(dir_path: Path, meta: dict) -> None:
    """写入 .meta.json。"""
    meta_file = dir_path / ".meta.json"
    meta_file.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


class CreateCollectionRequest(BaseModel):
    name: str
    icon: str = "BookOutlined"
    color: str = "#1677ff"


@app.post("/api/collections/create")
def create_collection(req: CreateCollectionRequest) -> dict:
    """新建一个空知识库分类（创建目录）。"""
    name = validate_collection_name(req.name)
    target_dir = DOCS_DIR / name
    if target_dir.exists():
        raise HTTPException(status_code=400, detail=f"「{name}」已存在")
    target_dir.mkdir(parents=True, exist_ok=True)
    _write_collection_meta(target_dir, {"icon": req.icon, "color": req.color})
    return {"message": f"已创建知识库「{name}」"}


class UpdateCollectionIconRequest(BaseModel):
    name: str
    icon: str = ""
    color: str = ""


@app.post("/api/collections/update-icon")
def update_collection_icon(req: UpdateCollectionIconRequest) -> dict:
    """更新知识库图标和/或颜色。"""
    name = validate_collection_name(req.name)
    target_dir = DOCS_DIR / name
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail=f"「{name}」不存在")
    meta = _read_collection_meta(target_dir)
    if req.icon:
        meta["icon"] = req.icon
    if req.color:
        meta["color"] = req.color
    _write_collection_meta(target_dir, meta)
    return {"message": f"已更新「{name}」外观"}


class RenameCollectionRequest(BaseModel):
    old_name: str
    new_name: str


@app.post("/api/collections/rename")
def rename_collection(req: RenameCollectionRequest) -> dict:
    """重命名知识库分类：移动目录 + 更新向量库 metadata。"""
    old = validate_collection_name(req.old_name)
    new = validate_collection_name(req.new_name)
    if old == new:
        raise HTTPException(status_code=400, detail="新旧名称相同")

    src_dir = DOCS_DIR / old
    if not src_dir.exists():
        raise HTTPException(status_code=404, detail=f"「{old}」不存在")
    dst_dir = DOCS_DIR / new
    if dst_dir.exists():
        raise HTTPException(status_code=400, detail=f"「{new}」已存在")

    # 1. 移动物理目录
    src_dir.rename(dst_dir)
    logger.info("目录已重命名：%s -> %s", old, new)

    # 2. 更新向量库中所有相关 chunks 的 metadata
    vector_collection = get_collection()
    data = vector_collection.get(where={"collection": old})
    ids = data.get("ids", [])
    metadatas = data.get("metadatas", [])
    documents = data.get("documents", [])

    if ids:
        # 删除旧的
        vector_collection.delete(ids=ids)
        # 用新 collection 名重新写入
        new_metas = []
        for m in metadatas:
            m_copy = dict(m)
            m_copy["collection"] = new
            new_metas.append(m_copy)
        new_ids = [f"{new}:{id.split(':', 1)[1]}" if ":" in id else f"{new}:{id}" for id in ids]
        vector_collection.add(ids=new_ids, documents=documents, metadatas=new_metas)
        logger.info("向量库已更新：%d 块 %s -> %s", len(ids), old, new)

    return {"message": f"已将「{old}」重命名为「{new}」"}


class DeleteCollectionRequest(BaseModel):
    name: str


@app.post("/api/collections/delete")
def delete_collection(req: DeleteCollectionRequest) -> dict:
    """删除整个知识库分类：移除所有 chunks + 删除目录。"""
    name = validate_collection_name(req.name)
    target_dir = DOCS_DIR / name
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail=f"「{name}」不存在")

    # 1. 从向量库删除该分类下所有 chunks
    vector_collection = get_collection()
    vector_collection.delete(where={"collection": name})

    # 2. 删除物理目录
    shutil.rmtree(target_dir)
    logger.info("已删除知识库：%s", name)

    return {"message": f"已删除知识库「{name}」"}


class CollectionInfo(BaseModel):
    name: str
    documents: list[str]
    total_chunks: int
    icon: str = "BookOutlined"
    color: str = "#1677ff"


class DocumentDetail(BaseModel):
    source: str
    page: int | None
    text: str
    score: float


@app.get("/api/collections")
def list_collections() -> list[CollectionInfo]:
    """获取已上传的知识库列表（按分类聚合），包含空目录分类。"""
    try:
        collection = get_collection()
        data = collection.get(include=["metadatas"])
        metadatas = data.get("metadatas", [])
        
        # 按 collection 分组
        groups: dict[str, dict[str, set]] = {}
        for meta in metadatas:
            coll = meta.get("collection", "未知")
            source = meta.get("source", "未知")
            if coll not in groups:
                groups[coll] = {"documents": set(), "count": 0}
            groups[coll]["documents"].add(source)
            groups[coll]["count"] += 1
        
        # 扫描文件系统，补充空目录分类
        if DOCS_DIR.exists():
            for d in DOCS_DIR.iterdir():
                if d.is_dir() and not d.name.startswith(".") and d.name != "_tmp":
                    if d.name not in groups:
                        # 从目录中读取文件列表作为 documents
                        files = {f.name for f in d.iterdir() if f.suffix.lower() in ALLOWED_EXT}
                        groups[d.name] = {"documents": files, "count": 0}
        
        return [
            CollectionInfo(
                name=coll,
                documents=sorted(info["documents"]),
                total_chunks=info["count"],
                icon=_read_collection_meta(DOCS_DIR / coll).get("icon", "BookOutlined"),
                color=_read_collection_meta(DOCS_DIR / coll).get("color", "#1677ff"),
            )
            for coll, info in sorted(groups.items())
        ]
    except Exception as e:
        logger.exception("获取知识库列表失败")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/collections/{collection_name}/documents")
def get_documents(collection_name: str) -> list[DocumentDetail]:
    """获取某个知识库下的所有文档片段。"""
    try:
        collection = get_collection()
        # 查询该分类下的所有数据（用空查询 + 过滤）
        result = collection.get(
            where={"collection": collection_name},
            include=["metadatas", "documents"],
        )
        
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])
        
        return [
            DocumentDetail(
                source=meta.get("source", "未知"),
                page=meta.get("page"),
                text=doc,
                score=1.0,  # 这里没有相似度分数，默认 1.0
            )
            for doc, meta in zip(documents, metadatas)
        ]
    except Exception as e:
        logger.exception("获取文档详情失败")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/collections/{collection_name}/raw/{filename}")
def get_raw_document(collection_name: str, filename: str) -> dict:
    """获取原始文档内容（未切割）。"""
    try:
        file_path = DOCS_DIR / collection_name / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 读取文件内容
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            # PDF 用 document_loader 读取，返回的是列表，需要合并
            from document_loader import load_file
            content_list = load_file(file_path, collection_name, filename)
            if isinstance(content_list, list):
                # 合并所有页面的文本
                content = "\n\n".join([item.get("text", "") if isinstance(item, dict) else str(item) for item in content_list])
            else:
                content = str(content_list)
        elif ext in {".md", ".txt"}:
            content = file_path.read_text(encoding="utf-8")
        else:
            raise HTTPException(status_code=400, detail="不支持的文件类型")
        
        return {
            "filename": filename,
            "collection": collection_name,
            "content": content,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取原始文档失败")
        raise HTTPException(status_code=500, detail=str(e))
