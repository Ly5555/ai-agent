"""向量库封装：Chroma 持久化 + 入库 + 查询。

所有仓库共用一个 collection（warehouse_kb），靠 metadata.warehouse 过滤隔离，
新增仓库零成本，也支持跨仓检索。

数据位置（扁平化后）：
    向量库：<repo>/data/chroma
    文档：  <repo>/data/docs/<仓库名>/*.pdf|md|txt
    上传：  <repo>/data/uploads/

运行（在 backend/ 下，扫描并入库所有仓库文档）：
    .venv/bin/python vector_store.py
"""
from pathlib import Path
from typing import Any

import chromadb

from chunker import split_chunks
from config import settings
from document_loader import load_file
from embeddings import embed_texts

# backend/ 目录（本文件在 backend/vector_store.py，parents[1] 即仓库根）
REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "data" / "docs"
CHROMA_DIR = REPO_ROOT / "data" / "chroma"
COLLECTION_NAME = "warehouse_kb"


def get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},  # 相似度用余弦距离
    )


def ingest_file(path: Path, warehouse: str) -> int:
    """入库单个文件，返回写入的块数。"""
    texts, metadatas = split_chunks(load_file(path, warehouse))
    if not texts:
        return 0

    vectors = embed_texts(texts)

    collection = get_collection()
    # 幂等：同仓库同文件名的旧块先删掉，重跑不会翻倍（chroma 多条件过滤需用 $and 组合）
    collection.delete(where={"$and": [{"warehouse": warehouse}, {"source": path.name}]})

    ids = [f"{warehouse}:{path.name}:{i}" for i in range(len(texts))]
    collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=vectors)
    return len(texts)


def ingest_all() -> None:
    """扫描 data/docs/<仓库名>/ 下所有支持的文件，逐仓库入库。"""
    total = 0
    for warehouse_dir in sorted(DOCS_DIR.iterdir()):
        if not warehouse_dir.is_dir():
            continue
        warehouse = warehouse_dir.name
        for file in sorted(warehouse_dir.iterdir()):
            if file.suffix.lower() not in {".pdf", ".md", ".txt"}:
                continue
            count = ingest_file(file, warehouse)
            total += count
            print(f"[{warehouse}] {file.name} -> {count} 块")
    collection = get_collection()
    print(f"入库完成：本次共 {total} 块，库内现有 {collection.count()} 块")


def query(question: str, warehouse: str | None = None, top_k: int = 4) -> list[dict[str, Any]]:
    """检索 top_k 个相关块（面试核心：retrieve 节点会调它）。"""
    collection = get_collection()
    where = {"warehouse": warehouse} if warehouse else None
    res = collection.query(
        query_embeddings=embed_texts([question]),
        n_results=top_k,
        where=where,
    )
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    return [{"text": d, "metadata": m} for d, m in zip(docs, metas)]


if __name__ == "__main__":
    ingest_all()
