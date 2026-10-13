"""文档加载：PDF 逐页 / Markdown·TXT 整读，产出带 metadata 的文本单元。"""
import io
import logging
from pathlib import Path
from typing import Any

from pypdf import PdfReader

logger = logging.getLogger("ai-knowledge-agent")


def _extract_pdf_pages(path: Path) -> list[tuple[str, int]]:
    """逐页抽 PDF 文字，返回 [(text, page_no), ...]。

    抽取优先级（文字层越弱越往后退）：
        1) PyMuPDF（fitz）——能救回嵌入字体缺 ToUnicode 的设计工具 PDF；
        2) pypdf——兜底文本引擎；
        3) OCR（PyMuPDF 渲染成图 + RapidOCR/pytesseract）——图片型/扫描件，文字层为空时启用。
    三路都抽不到才抛 ValueError。
    """
    # 1) PyMuPDF
    try:
        import fitz

        doc = fitz.open(str(path))
        pages = [(page.get_text().strip(), i + 1) for i, page in enumerate(doc)]
        if any(t for t, _ in pages):
            logger.info(
                "PDF 提取引擎：PyMuPDF（fitz），页数=%d，有文字 %d 页",
                doc.page_count,
                sum(1 for t, _ in pages if t),
            )
            return pages
        logger.info("PyMuPDF 抽到 %d 页但无文字，转 pypdf 兜底", doc.page_count)
    except ImportError:
        logger.info("PyMuPDF 未安装，回退 pypdf 提取引擎：%s", path.name)

    # 2) pypdf 兜底
    try:
        reader = PdfReader(str(path))
        pages = [((page.extract_text() or "").strip(), i + 1) for i, page in enumerate(reader.pages)]
        if any(t for t, _ in pages):
            logger.info("PDF 提取引擎：pypdf，有文字 %d 页", sum(1 for t, _ in pages if t))
            return pages
    except Exception as e:  # pypdf 解析异常也走 OCR
        logger.warning("pypdf 解析异常：%s", e)

    # 3) OCR 兜底（图片型/扫描件 PDF）
    logger.info("文字层为空，尝试 OCR 提取：%s", path.name)
    return _ocr_pdf_pages(path)


_RAPIDOCR_ENGINE = None


def _get_rapidocr():
    """惰性加载 RapidOCR 引擎（模块级缓存，避免每次入库都重载模型）。"""
    global _RAPIDOCR_ENGINE
    if _RAPIDOCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR

        _RAPIDOCR_ENGINE = RapidOCR()
    return _RAPIDOCR_ENGINE


def _ocr_pdf_pages(path: Path) -> list[tuple[str, int]]:
    """图片型 PDF 用 OCR 抽文字。

    渲染：PyMuPDF（fitz）把每页渲染成图，不需要系统装 poppler。
    识别：优先 RapidOCR（纯 pip、自带中文模型、无需任何系统二进制）；
          rapidocr 缺失或失败时回退 pytesseract（需系统装 tesseract + chi_sim）。
    """
    import fitz  # 渲染页面成图（必装依赖，免 poppler）

    pages: list[tuple[str, int]] | None = None

    # 1) 主引擎：RapidOCR（onnxruntime，无系统依赖）
    try:
        import numpy as np

        engine = _get_rapidocr()
        doc = fitz.open(str(path))
        pages = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=200)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:  # 去掉 alpha 通道
                img = img[:, :, :3]
            img = img[:, :, ::-1].copy()  # RGB -> BGR（OpenCV/rapidocr 约定）
            result, _ = engine(img)
            text = "\n".join([r[1] for r in result]) if result else ""
            pages.append((text.strip(), i + 1))
        logger.info("OCR 引擎：RapidOCR（onnxruntime，无系统依赖）")
    except ImportError:
        logger.info("rapidocr 未安装，回退 pytesseract OCR 引擎")
    except Exception as e:
        logger.warning("RapidOCR 识别失败，回退 pytesseract：%s", e)
        pages = None

    # 2) 回退引擎：pytesseract（需系统 tesseract + chi_sim）
    if pages is None:
        try:
            from PIL import Image
            import pytesseract
        except ImportError as e:
            miss = "pytesseract" if "pytesseract" in str(e) else "Pillow"
            raise ValueError(
                f"PDF 无可提取文字层且 OCR 未配置：{path.name}（图片型 PDF，fitz 与 pypdf 都抽不到）。"
                f"请安装 OCR 依赖：`pip install rapidocr-onnxruntime`（推荐，纯 pip 无系统依赖），"
                f"或 `pip install pytesseract pillow` + 系统 `brew install tesseract tesseract-lang`（macOS）；"
                f"也可将源文件替换为带文字层的 PDF。"
            )
        try:
            doc = fitz.open(str(path))
            pages = []
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text = pytesseract.image_to_string(img, lang="chi_sim+eng").strip()
                pages.append((text, i + 1))
            logger.info("OCR 引擎：pytesseract（系统 tesseract）")
        except Exception as e:
            raise ValueError(
                f"PDF OCR 失败（需系统装 tesseract 及 chi_sim 语言包）：{path.name}。原错误：{e}"
            )

    if not any(t for t, _ in pages):
        raise ValueError(
            f"PDF OCR 后仍无可提取文字：{path.name}（扫描质量过低或纯图无文字），请更换更清晰的源文件。"
        )
    logger.info("OCR 提取完成：%s 共 %d 页", path.name, len(pages))
    return pages


def load_file(
    path: Path, collection: str, source_name: str | None = None
) -> list[dict[str, Any]]:
    """把一个文件读成 [{text, metadata}, ...]，PDF 逐页提取。"""
    docs: list[dict[str, Any]] = []
    if path.suffix.lower() == ".pdf":
        pages = _extract_pdf_pages(path)
        logger.info(
            "PDF 提取结果：%s 共 %d 页，有文字 %d 页",
            path.name,
            len(pages),
            sum(1 for t, _ in pages if t),
        )
        if not any(t for t, _ in pages):
            logger.warning("PDF 无文字层：%s", path.name)
            raise ValueError(
                f"PDF 无可提取文字层：{path.name}（设计工具/图片型 PDF，"
                f"fitz、pypdf、OCR 均未能抽出文字，请更换带文字层的源文件或提高扫描清晰度）"
            )
        for text, page_no in pages:
            if text:
                docs.append({"text": text, "page": page_no})
    else:  # .md / .txt 直接整读
        text = path.read_text(encoding="utf-8").strip()
        if text:
            docs.append({"text": text, "page": 1})
    for d in docs:
        d["metadata"] = {
            "collection": collection,
            "source": source_name or path.name,
            "page": d["page"],
            "type": "note",
        }
    return docs
