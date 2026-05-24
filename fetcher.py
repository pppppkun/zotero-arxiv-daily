import logging
import time
import xml.etree.ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
MAX_RETRIES = 5
RETRY_BASE_DELAY = 10  # 秒


def _fetch_page(query: str, start: int, max_results: int) -> ET.Element:
    """请求 arXiv API 单页，带指数退避重试。"""
    params = {
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": start,
        "max_results": max_results,
    }
    # 绕过系统 HTTP 代理（代理的 HTTPS CONNECT 对 arXiv 有 SSL 问题），直连即可
    client = httpx.Client(trust_env=False)
    for attempt in range(MAX_RETRIES):
        try:
            r = client.get(ARXIV_API, params=params, timeout=30)
            if r.status_code == 200:
                return ET.fromstring(r.text)
            if r.status_code in (429, 503):
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning("arXiv returned %d, retrying in %ds (attempt %d/%d)",
                               r.status_code, delay, attempt + 1, MAX_RETRIES)
                time.sleep(delay)
                continue
            r.raise_for_status()
        except httpx.TimeoutException:
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning("arXiv request timed out, retrying in %ds (attempt %d/%d)",
                           delay, attempt + 1, MAX_RETRIES)
            time.sleep(delay)
    raise RuntimeError(f"arXiv API failed after {MAX_RETRIES} retries for query: {query}")


def _parse_entries(root: ET.Element) -> list[dict]:
    """解析 Atom feed 中的 entry 节点为论文字典。"""
    papers = []
    for entry in root.findall("atom:entry", ATOM_NS):
        # 跳过错误条目（arXiv 有时返回 <entry><id>http://arxiv.org/api/errors</id>...）
        entry_id_el = entry.find("atom:id", ATOM_NS)
        if entry_id_el is not None and "errors" in entry_id_el.text:
            continue

        entry_id = entry_id_el.text.strip() if entry_id_el is not None else ""
        title_el = entry.find("atom:title", ATOM_NS)
        summary_el = entry.find("atom:summary", ATOM_NS)
        published_el = entry.find("atom:published", ATOM_NS)

        title = title_el.text.strip() if title_el is not None else ""
        abstract = summary_el.text.strip().replace("\n", " ") if summary_el is not None else ""
        published_raw = published_el.text[:10] if published_el is not None else ""  # YYYY-MM-DD

        authors = [a.find("atom:name", ATOM_NS).text
                    for a in entry.findall("atom:author", ATOM_NS)
                    if a.find("atom:name", ATOM_NS) is not None]

        # arXiv Atom feed 用 arxiv:primaryCategory 和 category 标签
        categories = [c.get("term") for c in entry.findall("atom:category", ATOM_NS)]

        papers.append({
            "id": entry_id,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "published": published_raw,
            "categories": categories,
            "url": entry_id,
        })
    return papers


def fetch_papers(categories: list[str], max_results: int, date: str) -> list[dict]:
    """从 arXiv 拉取指定分类、指定日期的论文，去重后返回。

    使用 submittedDate 过滤 + 客户端兜底，确保只返回当天新论文。
    直接使用 httpx 请求，自主控制重试和延迟，避免 arxiv 库的限速问题。
    """
    date_compact = date.replace("-", "")

    seen_ids: set[str] = set()
    papers: list[dict] = []

    for cat in categories:
        logger.info("Fetching category: %s for date %s", cat, date)
        query = f"cat:{cat} AND submittedDate:[{date_compact}000000 TO {date_compact}235959]"

        try:
            root = _fetch_page(query, start=0, max_results=max_results)
            entries = _parse_entries(root)

            for p in entries:
                if p["id"] in seen_ids:
                    continue
                # 客户端兜底：只保留指定日期的论文
                if p["published"] != date:
                    continue
                seen_ids.add(p["id"])
                papers.append(p)

            logger.info("  %s: %d papers", cat, len([p for p in entries if p["published"] == date]))
        except Exception:
            logger.exception("Failed to fetch category %s", cat)

        # 分类间延迟
        time.sleep(3)

    logger.info("Fetched %d unique papers across %d categories", len(papers), len(categories))
    return papers
