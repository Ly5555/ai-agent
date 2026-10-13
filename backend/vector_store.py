"""向量库封装：Chroma 持久化 + 入库 + 查询。

所有个人资料共用一个 collection（personal_kb），靠 metadata.collection 过滤整理，
新增知识分类零成本，也支持跨分类检索。

数据位置（扁平化后）：
    向量库：<repo>/data/chroma
    文档：  <repo>/data/docs/<知识分类>/*.pdf|md|txt
    上传：  <repo>/data/uploads/

运行（在 backend/ 下，扫描并入库所有知识分类文档）：
    .venv/bin/python vector_store.py
"""
import logging
from pathlib import Path
from typing import Any

import chromadb

from chunker import split_chunks
from config import settings
from document_loader import load_file
from embeddings import embed_texts

logger = logging.getLogger("ai-knowledge-agent")

# backend/ 目录（本文件在 backend/vector_store.py，parents[1] 即仓库根）
REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "data" / "docs"
CHROMA_DIR = REPO_ROOT / "data" / "chroma"
COLLECTION_NAME = "personal_kb"


def get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},  # 相似度用余弦距离
    )


def ingest_file(
    path: Path, collection_name: str, source_name: str | None = None
) -> int:
    """入库单个文件，返回写入的块数。"""
    display_name = source_name or path.name
    logger.info("开始入库：%s (collection=%s)", path.name, collection_name)
    texts, metadatas = split_chunks(load_file(path, collection_name, display_name))
    if not texts:
        logger.warning("入库跳过：未切出任何文本块（%s）", display_name)
        return 0

    logger.info("文本切分为 %d 块，开始向量化（embedding）...", len(texts))
    vectors = embed_texts(texts)

    vector_collection = get_collection()
    # 幂等：同分类同文件名的旧块先删掉，重跑不会翻倍（chroma 多条件过滤需用 $and 组合）
    vector_collection.delete(
        where={"$and": [{"collection": collection_name}, {"source": display_name}]}
    )

    ids = [f"{collection_name}:{path.name}:{i}" for i in range(len(texts))]
    vector_collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=vectors)
    logger.info("向量库写入完成：collection=%s source=%s 块数=%d", collection_name, display_name, len(texts))
    return len(texts)


def ingest_all() -> None:
    """扫描 data/docs/<知识分类>/ 下所有支持的文件，逐分类入库。"""
    total = 0
    for collection_dir in sorted(DOCS_DIR.iterdir()):
        if not collection_dir.is_dir():
            continue
        collection_name = collection_dir.name
        for file in sorted(collection_dir.iterdir()):
            if file.suffix.lower() not in {".pdf", ".md", ".txt"}:
                continue
            try:
                count = ingest_file(file, collection_name)
            except Exception as e:  # 单个文件抽不到文字/入库失败，跳过不中断整库
                logger.warning("[跳过] %s/%s: %s", collection_name, file.name, e)
                continue
            total += count
            logger.info("[%s] %s -> %d 块", collection_name, file.name, count)
    collection = get_collection()
    logger.info("入库完成：本次共 %d 块，库内现有 %d 块", total, collection.count())


def query(question: str, collection_name: str, top_k: int = 4) -> list[dict[str, Any]]:
    """检索服务：向量相似度 top-k + 强制 metadata 过滤（按 collection 隔离）。

    参数：
        question: 用户问题
        collection_name: 知识库名（必填，强制带 where={"collection": ...} 过滤，不允许跨库检索）
        top_k: 返回块数
    返回：[{text, source, page, score, metadata}, ...]，score = 1 - cosine_distance
    """
    collection = get_collection()
    logger.info("检索请求：question=%r collection=%s top_k=%d", question, collection_name, top_k)
    res = collection.query(
        query_embeddings=embed_texts([question]),
        n_results=top_k,
        where={"collection": collection_name},  # 强制按 collection 过滤
    )
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    results = [
        {
            "text": d,
            "source": m.get("source"),
            "page": m.get("page"),
            "score": 1 - dists[i],  # cosine distance -> 相似度（越接近 1 越相关）
            "metadata": m,
        }
        for i, (d, m) in enumerate(zip(docs, metas))
    ]
    logger.info("检索命中 %d 块", len(results))
    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    ingest_all()
