"""中文友好的递归分块。"""
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter


# 中文文档友好的分隔符：先按段落切，切不开再按句切
SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=100,
    separators=["\n\n", "\n", "。", "；", "，", ""],
)


def split_chunks(docs: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    """逐条分块，metadata 随块继承（哪个仓、哪个文件、第几页）。"""
    texts: list[str] = []
    metadatas: list[dict[str, Any]] = []
    for d in docs:
        for chunk in SPLITTER.split_text(d["text"]):
            texts.append(chunk)
            metadatas.append(d["metadata"])
    return texts, metadatas
