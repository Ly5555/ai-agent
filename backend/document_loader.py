"""文档加载：PDF 逐页 / Markdown·TXT 整读，产出带 metadata 的文本单元。"""
from pathlib import Path
from typing import Any

from pypdf import PdfReader


def load_file(path: Path, warehouse: str) -> list[dict[str, Any]]:
    """把一个文件读成 [{text, metadata}, ...]，PDF 逐页提取。"""
    docs: list[dict[str, Any]] = []
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        for page_no, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                docs.append({"text": text, "page": page_no})
    else:  # .md / .txt 直接整读
        text = path.read_text(encoding="utf-8").strip()
        if text:
            docs.append({"text": text, "page": 1})
    for d in docs:
        d["metadata"] = {
            "warehouse": warehouse,
            "source": path.name,
            "page": d["page"],
            "type": "sop",
        }
    return docs
