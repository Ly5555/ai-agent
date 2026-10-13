"""FastAPI 入口：聊天接口 + 健康检查 + 文件上传入库。

扁平化后运行方式：
    cd backend && uvicorn main:app --reload --port 8000
"""
import logging
import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import ChatRequest, ChatResponse, run_agent
from config import settings
from vector_store import DOCS_DIR, ingest_file

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


@app.post("/api/upload", response_model=UploadResponse)
def upload(file: UploadFile = File(...), collection: str = Form(...)) -> UploadResponse:
    """保存一份原文档，并写入指定知识分类的向量库。"""
    collection_name = validate_collection_name(collection)
    filename = Path(file.filename or "").name
    ext = Path(filename).suffix.lower()
    logger.info("收到上传请求：collection=%s filename=%s ext=%s", collection_name, filename, ext)
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型 {ext}，仅支持 pdf/md/txt")
    if not filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    target_dir = DOCS_DIR / collection_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    with target.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    logger.info("原文档已保存：%s", target)

    try:
        count = ingest_file(target, collection_name, source_name=filename)
    except ValueError as e:
        # 可预期错误（如 PDF 无文字层）-> 400 友好提示，而不是笼统 500
        logger.warning("入库被拒（可预期错误）：%s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # 其它意外（embedding 接口/磁盘等）-> 500 但带上原因，方便排查
        logger.error("入库失败（意外错误）：%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"入库失败：{e}")
    return UploadResponse(
        message=f"入库 {count} 块",
        collection=collection_name,
        filename=filename,
        chunks=count,
    )
