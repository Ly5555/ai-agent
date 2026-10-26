"""沉淀 Agent（D14）：第二张 LangGraph 图，把知识缺口归纳成 FAQ 草稿。

问答图（agent.py）负责「消费知识」，这张图负责「生产知识」：
读 D12 攒下的真实知识缺口 → LLM 聚类归并 → 复用问答图取答案 → 落成人工可改的草稿。
D15 会把草稿灌回向量库，闭环完成。

流程（线性，无条件分支）：
    START → load_gaps → cluster_questions → draft_faqs → write_draft → END

设计约束：
  - 答案不许模型脑补。draft_faqs 对每个聚类问题真跑一遍问答图，
    取带检索依据的 answer；答不上的一律标「待补充」，宁缺毋滥。
  - 跑问答图时传 record_gap=False，否则 grounding 会把缺口再写回 gaps.jsonl，
    每跑一次沉淀就污染一次输入数据（自反馈）。

运行：
    cd backend && .venv/bin/python curator.py
"""
import json
import logging
import re
from pathlib import Path
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from agent import CITATION_MARK, NO_INFO_MARKERS, ChatRequest, run_agent
from config import make_http_client, settings

logger = logging.getLogger(__name__)

# 与 agent.py 的 _record_gap 落在同一个文件上
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GAPS_FILE = DATA_DIR / "gaps.jsonl"
DRAFT_FILE = DATA_DIR / "faq_draft.md"

# 目标聚类数：计划要求 20 条乱糟糟的输入归纳成 5~8 条
CLUSTER_MIN, CLUSTER_MAX = 5, 8


class CuratorState(TypedDict):
    raw_items: list[dict]  # load_gaps：去重后的缺口问题
    clusters: list[dict]  # cluster_questions：语义分组
    drafts: list[dict]  # draft_faqs：FAQ 草稿（含待补充）
    draft_path: str  # write_draft：落盘位置


def _llm():
    """与问答图同一套 LLM 配置（temperature=0，走直连智谱的 http_client）。"""
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0,
        http_client=make_http_client(),
    )


# ---------- 节点 1：读缺口 ----------
def load_gaps(state: CuratorState) -> dict:
    """读 data/gaps.jsonl，按 query 去重。

    这个文件是 append 写的，可能混进空行或半截脏行，逐行容错跳过。
    注意 collection 经常是空串（route 没定库时就是空），只能当提示，不能当分组依据。
    """
    if not GAPS_FILE.exists():
        logger.warning("缺口文件不存在：%s", GAPS_FILE)
        return {"raw_items": []}

    seen: set[str] = set()
    items: list[dict] = []
    bad_lines = 0

    for line in GAPS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            bad_lines += 1
            continue

        query = str(rec.get("query", "")).strip()
        if not query or query in seen:
            continue
        seen.add(query)
        items.append(
            {
                "query": query,
                "collection": str(rec.get("collection", "")).strip(),
                "timestamp": str(rec.get("timestamp", "")),
            }
        )

    total = len(GAPS_FILE.read_text(encoding="utf-8").splitlines())
    logger.info(
        "load_gaps：文件 %d 行 → 脏行 %d → 去重后 %d 条缺口",
        total, bad_lines, len(items),
    )
    return {"raw_items": items}


# ---------- 节点 2：LLM 聚类 ----------
def _fallback_clusters(items: list[dict]) -> list[dict]:
    """聚类失败时的退化方案：按 collection 分组，空 collection 单独一组。"""
    valid_colls = set(_available_collections())
    groups: dict[str, list[str]] = {}
    for it in items:
        coll = it["collection"] if it["collection"] in valid_colls else ""
        key = coll or "未分类"
        groups.setdefault(key, []).append(it["query"])
    return [
        {"question": qs[0], "members": qs, "collection": "" if key == "未分类" else key}
        for key, qs in groups.items()
    ]


def _parse_clusters(text: str, items: list[dict]) -> list[dict]:
    """三层兜底解析：直接 loads → 截取 [...] → 退化成按 collection 分组。

    模型很爱在 JSON 前后加解释文字，所以必须有截取这一层。
    members 用 1 开始的序号引用原始问题，解析时换回真实 query。
    """
    candidates = [text.strip()]
    # 剥掉 ```json ... ``` 代码围栏
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        candidates.append(fence.group(1).strip())
    # 截取第一个 [ 到最后一个 ]
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    seen_idxs: set[int] = set()  # 模型偶尔把同一条问题塞进两个组，序号只认第一次
    for cand in candidates:
        if not cand:
            continue
        try:
            data = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, list):
            continue

        valid_colls = set(_available_collections())
        clusters: list[dict] = []
        for grp in data:
            if not isinstance(grp, dict):
                continue
            question = str(grp.get("question", "")).strip()
            idxs = grp.get("members") or grp.get("ids") or []
            if not question or not isinstance(idxs, list):
                continue
            members: list[str] = []
            for i in idxs:
                if not isinstance(i, int) or not 1 <= i <= len(items) or i in seen_idxs:
                    continue
                seen_idxs.add(i)
                members.append(items[i - 1]["query"])
            if not members:
                continue
            # 分类不许编：库里没有的分类只会让后面的检索空转
            coll = str(grp.get("collection", "")).strip()
            clusters.append(
                {
                    "question": question,
                    "members": members,
                    "collection": coll if coll in valid_colls else "",
                }
            )
        if clusters:
            return clusters

    logger.warning("聚类结果解析失败，退化成按 collection 分组")
    return _fallback_clusters(items)


def _available_collections() -> list[str]:
    """从 data/docs/ 实际目录取候选分类，别让提示词写死一份和库不一致的清单。"""
    from vector_store import DOCS_DIR  # 延迟导入：只用常量，避免沉淀脚本强依赖 chroma

    if not DOCS_DIR.exists():
        return []
    return sorted(
        d.name for d in DOCS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(("_", "."))
    )


def cluster_questions(state: CuratorState) -> dict:
    """把一批杂乱缺口问题归并成 5~8 个规范问题。"""
    items = state.get("raw_items", [])
    if not items:
        logger.warning("没有缺口记录可聚类")
        return {"clusters": []}

    if not settings.llm_api_key:
        logger.warning("未配置 LLM key，退化成按 collection 分组")
        return {"clusters": _fallback_clusters(items)}

    listing = "\n".join(
        f"{i}. {it['query']}" + (f"（原分类：{it['collection']}）" if it["collection"] else "")
        for i, it in enumerate(items, 1)
    )
    colls = _available_collections()
    coll_rule = (
        f"- collection 只能从这些已有分类里选一个最贴切的：{' / '.join(colls)}；"
        "实在判断不了就留空字符串\n"
        if colls
        else "- collection 留空字符串\n"
    )
    prompt = (
        "你在整理一个个人知识库的「查不到的问题」清单。\n"
        f"请把下面 {len(items)} 条问题按主题归并成 {CLUSTER_MIN}~{CLUSTER_MAX} 组。\n"
        "归并尺度：同一个知识点/同一类主题的问题要合并（比如各种问法的「Python 装饰器」算一组）；"
        "主题明显不同的不许凑在一组（比如「量子计算」和「虚拟 DOM」不能算一组）。\n"
        f"如果合完超过 {CLUSTER_MAX} 组，就把主题最接近的继续合；"
        f"如果不足 {CLUSTER_MIN} 组，说明合过头了，请拆开。\n\n"
        "只输出 JSON 数组，不要任何解释、不要代码围栏。格式：\n"
        '[{"question": "规范问题表述", "members": [1, 5, 12], "collection": "所属知识分类"}]\n\n'
        "要求：\n"
        "- members 填归并进该组的原始问题序号（整数），每个序号只能出现一次\n"
        f"{coll_rule}"
        "- 不要新增问题，不要遗漏问题\n"
        "- question 写成可直接当 FAQ 标题的规范表述，不要「其他问题」这种没信息量的\n\n"
        f"原始问题清单：\n{listing}"
    )

    def _ask(extra: str = "") -> list[dict]:
        raw = _llm().invoke(prompt + extra).content
        return _parse_clusters(str(raw), items)

    try:
        clusters = _ask()
        # 组数不达标就带着具体反馈重试一次：沉淀质量全靠这一步，值得多花一次调用
        if not CLUSTER_MIN <= len(clusters) <= CLUSTER_MAX:
            hint = (
                f"\n\n【上一次输出不合格：你给了 {len(clusters)} 组，不在 {CLUSTER_MIN}~{CLUSTER_MAX} 组范围内。"
                f"请重新归并，把主题最接近的组继续合并到 {CLUSTER_MAX} 组以内，"
                "合并不了的宁可留一个稍宽的主题也不许拆成十几组。】"
                if len(clusters) > CLUSTER_MAX
                else f"\n\n【上一次输出不合格：你只给了 {len(clusters)} 组，不足 {CLUSTER_MIN} 组，合并过度。请拆开。】"
            )
            logger.info("聚类组数 %d 不在 %d~%d，带反馈重试一次", len(clusters), CLUSTER_MIN, CLUSTER_MAX)
            try:
                retried = _ask(hint)
                if CLUSTER_MIN <= len(retried) <= CLUSTER_MAX:
                    clusters = retried
                else:
                    logger.warning("重试后仍为 %d 组，沿用第一次结果", len(retried))
            except Exception:  # noqa: BLE001
                logger.exception("聚类重试失败，沿用第一次结果")

        covered = {q for c in clusters for q in c["members"]}
        logger.info(
            "cluster_questions：%d 条缺口 → %d 组（覆盖 %d/%d 条）",
            len(items), len(clusters), len(covered), len(items),
        )
        if len(covered) < len(items):
            # 模型漏掉的问题自成一组补回来，保证不丢数据
            missing = [it["query"] for it in items if it["query"] not in covered]
            logger.info("聚类漏掉 %d 条，补为独立组：%s", len(missing), missing[:5])
            clusters += _fallback_clusters(
                [{"query": q, "collection": "", "timestamp": ""} for q in missing]
            )
        return {"clusters": clusters}
    except Exception:  # noqa: BLE001
        logger.exception("聚类调用失败，退化成按 collection 分组")
        return {"clusters": _fallback_clusters(items)}


# ---------- 节点 3：复用问答图取答案 ----------
def _has_no_info(text: str) -> bool:
    """命中任一「查不到」措辞就算没答上。复用 agent.py 的常量，避免两边规则漂移。"""
    return any(m in text for m in NO_INFO_MARKERS)


def draft_faqs(state: CuratorState) -> dict:
    """每个聚类问题真跑一遍问答图取答案；答不上的标待补充，不编造。"""
    clusters = state.get("clusters", [])
    drafts: list[dict] = []

    for i, cluster in enumerate(clusters, 1):
        question = cluster["question"]
        collection = cluster.get("collection", "")
        intent = ""  # 跑图失败时保持空串，别让 resp 未绑定炸掉整个沉淀
        try:
            # record_gap=False：沉淀时不许往 gaps.jsonl 写，否则自反馈污染输入
            resp = run_agent(
                ChatRequest(query=question, history=[], collection=collection),
                record_gap=False,
            )
            answer = (resp.answer or "").strip()
            intent = resp.intent or ""
        except Exception:  # noqa: BLE001
            logger.exception("draft_faqs：跑问答图失败 | question=%r", question)
            answer = ""

        # 来源就在答案末尾那行「引用来源：…」里，单独拆出来方便人工核对
        source = ""
        if CITATION_MARK in answer:
            answer, _, source = answer.partition(CITATION_MARK)
            source = source.strip()
            answer = answer.strip()

        # 三条都满足才算「有依据的答案」：
        #   有正文 / 没说查不到 / 引用来源里真列了资料N。
        # 最后一条是关键——「引用来源：无」说明答案是模型脑补的常识，不能进 FAQ。
        has_basis = "资料" in source
        answered = bool(answer) and not _has_no_info(answer) and has_basis
        if answered is False and bool(answer) and not has_basis:
            logger.info("draft_faqs：无检索依据（%s），判为待补充 | %r", source or "无来源行", question)

        drafts.append(
            {
                "question": question,
                "answer": answer,
                "source": source,
                "collection": collection,
                "members": cluster.get("members", []),
                "answered": answered,
                "intent": intent,
            }
        )
        logger.info(
            "draft_faqs [%d/%d] %s | %r | 归并 %d 条",
            i, len(clusters), "✓" if answered else "待补充", question,
            len(cluster.get("members", [])),
        )

    ok = sum(1 for d in drafts if d["answered"])
    logger.info("draft_faqs 完成：%d 条草稿，其中有答案 %d 条、待补充 %d 条",
                len(drafts), ok, len(drafts) - ok)
    return {"drafts": drafts}


# ---------- 节点 4：落盘 ----------
def write_draft(state: CuratorState) -> dict:
    """输出人工可改的 Markdown 草稿。D14 不入库，入库是 D15 的 POST /api/curate。"""
    drafts = state.get("drafts", [])
    answered = [d for d in drafts if d["answered"]]
    pending = [d for d in drafts if not d["answered"]]

    lines = [
        "# FAQ 草稿（D14 沉淀 Agent 自动生成）",
        "",
        f"> 输入缺口 {len(state.get('raw_items', []))} 条 → 聚类 {len(drafts)} 组"
        f" → 有依据 {len(answered)} 条 / 待补充 {len(pending)} 条",
        "> 答案均来自知识库检索结果，未答上的不编造，只列在「待补充」。",
        "> 人工审核后可由 D15 的 /api/curate 灌回向量库。",
        "",
    ]

    for d in answered:
        lines += [f"## {d['question']}", ""]
        if d["collection"]:
            lines += [f"- **知识分类**：{d['collection']}", ""]
        lines += [d["answer"], ""]
        if d["source"]:
            lines += [f"> 来源：{d['source']}", ""]
        if len(d["members"]) > 1:
            lines += [f"> 归并自 {len(d['members'])} 条原始缺口：" + "；".join(d["members"]), ""]

    if pending:
        lines += ["---", "", "## 待补充（知识库里确实没有）", ""]
        for d in pending:
            lines += [f"- {d['question']}" + (f"（分类：{d['collection']}）" if d["collection"] else "")]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DRAFT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("write_draft：草稿已落盘 %s", DRAFT_FILE)
    return {"draft_path": str(DRAFT_FILE)}


# ---------- D15：解析草稿，供 /api/curate 入库 ----------
def parse_faq_draft(path: str | Path) -> list[dict]:
    """D15：解析 write_draft 产出的 FAQ 草稿 Markdown，提取可入库的 FAQ。

    草稿格式（write_draft 当前版）：
        ## <问题>                  <- 一条 FAQ 的标题，作为 question
        - **知识分类**：<分类>      <- 该 FAQ 归属的知识库（route 按此路由）
        <答案正文>
        > 来源：...                <- 跳过（FAQ 入库后引用来源会重写）
        > 归并自 N 条原始缺口：...   <- 跳过

        ## 待补充（知识库里确实没有）  <- 之后全部跳过，不入库
        - ...

    只返回有答案（answer 非空）且非「待补充」区的 FAQ；每条带 question/answer/collection。
    """
    p = Path(path)
    if not p.exists():
        logger.warning("FAQ 草稿不存在：%s", p)
        return []

    faqs: list[dict] = []
    cur: dict | None = None
    in_pending = False

    def flush() -> None:
        nonlocal cur
        if cur and cur.get("question"):
            answer = "\n".join(cur["answer_lines"]).strip()
            if answer:
                faqs.append(
                    {
                        "question": cur["question"],
                        "answer": answer,
                        "collection": cur["collection"],
                    }
                )
        cur = None

    for raw in p.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        # 待补充区：之后全部跳过（这些知识库里确实没有，不能编进 FAQ）
        if s.startswith("## ") and "待补充" in s:
            flush()
            in_pending = True
            continue
        if in_pending:
            continue
        # 新 FAQ 标题
        if s.startswith("## "):
            flush()
            cur = {"question": s[3:].strip(), "collection": "", "answer_lines": []}
            continue
        if cur is None:
            continue  # 顶部引用块等，跳过
        # 知识分类行
        m = re.match(r"-\s*\*\*知识分类\*\*[:：]\s*(.+?)\s*$", s)
        if m:
            cur["collection"] = m.group(1).strip()
            continue
        # 引用块（来源 / 归并）与分隔线：跳过
        if s.startswith("> ") or s.startswith("[资料") or s.startswith("---"):
            continue
        # 其余视为答案正文
        if s:
            cur["answer_lines"].append(s)
    flush()
    logger.info("parse_faq_draft：解析出 %d 条可入库 FAQ", len(faqs))
    return faqs


# ---------- 图 ----------
def build_curator_graph():
    """构建并编译沉淀图。与问答图并列的第二张 LangGraph 图。"""
    graph = StateGraph(CuratorState)
    graph.add_node("load_gaps", load_gaps)
    graph.add_node("cluster_questions", cluster_questions)
    graph.add_node("draft_faqs", draft_faqs)
    graph.add_node("write_draft", write_draft)

    graph.add_edge(START, "load_gaps")
    graph.add_edge("load_gaps", "cluster_questions")
    graph.add_edge("cluster_questions", "draft_faqs")
    graph.add_edge("draft_faqs", "write_draft")
    graph.add_edge("write_draft", END)
    return graph.compile()


def run_curator() -> dict:
    """跑一次沉淀，返回统计结果（供 D15 的 /api/curate 直接复用）。"""
    out = build_curator_graph().invoke(
        {"raw_items": [], "clusters": [], "drafts": [], "draft_path": ""}
    )
    drafts = out.get("drafts", [])
    return {
        "gaps": len(out.get("raw_items", [])),
        "clusters": len(out.get("clusters", [])),
        "drafts": len(drafts),
        "answered": sum(1 for d in drafts if d["answered"]),
        "pending": sum(1 for d in drafts if not d["answered"]),
        "draft_path": out.get("draft_path", ""),
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    stat = run_curator()
    print(
        f"\n缺口 {stat['gaps']} 条 → 聚类 {stat['clusters']} 组 → "
        f"草稿 {stat['drafts']} 条（有依据 {stat['answered']}，待补充 {stat['pending']}）\n"
        f"已写入：{stat['draft_path']}"
    )
