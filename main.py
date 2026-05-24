#!/usr/bin/env python3
"""arXiv Daily Fetcher — 每日拉取 arXiv 论文，按关键词相似度排序，邮件推送。

Usage:
  uv run python main.py              # 正式运行（今天）
  uv run python main.py --date 2026-05-20  # 指定日期
  uv run python main.py --mock       # 用样本数据测试
  uv run python main.py --dry-run    # 真实拉取，不发邮件，存 HTML 预览
"""
import logging
import sys
from datetime import date
from pathlib import Path

import yaml

from fetcher import fetch_papers
from mailer import build_email, send_email
from mock_data import get_mock_papers
from similarity import SimilarityEngine
from summarizer import PaperSummarizer
from store import load as load_papers, save as save_papers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# 抑制第三方库的 HTTP 请求日志
for noisy in ["httpx", "huggingface_hub", "sentence_transformers", "urllib3"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)
logger = logging.getLogger("arxiv-daily")

TEST_OUTPUT_DIR = Path(__file__).parent / "test_output"


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_html_preview(html: str, label: str) -> None:
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = TEST_OUTPUT_DIR / "email.html"
    path.write_text(html, encoding="utf-8")
    logger.info("HTML preview saved to %s (%s)", path, label)


def main():
    mock_mode = "--mock" in sys.argv
    dry_run = "--dry-run" in sys.argv

    # 解析 --date YYYY-MM-DD
    date_label = None
    for i, arg in enumerate(sys.argv):
        if arg == "--date" and i + 1 < len(sys.argv):
            date_label = sys.argv[i + 1]

    if mock_mode:
        logger.info("MOCK MODE — using sample data, no arXiv API, no email")
    elif dry_run:
        logger.info("DRY RUN — real arXiv fetch, email preview only")
    else:
        logger.info("arXiv Daily Fetcher started")

    config = load_config()

    # 日期
    if date_label is None:
        date_label = "test" if mock_mode else date.today().isoformat()

    # 1. 拉取论文（mock 模式跳过 arXiv）
    if mock_mode:
        papers = get_mock_papers()
    else:
        papers = fetch_papers(
            categories=config["arxiv"]["categories"],
            max_results=config["arxiv"]["max_results_per_category"],
            date=date_label,
        )
        if not papers:
            logger.warning("No papers found, exiting")
            return

    # 2. 计算相似度并排序
    engine = SimilarityEngine(model_name=config["similarity"]["model_name"])
    ranked = engine.rank(
        papers=papers,
        keywords=config["keywords"],
        top_n=config["ranker"]["top_n"],
    )

    # 3. PDF 摘要（mock 模式跳过）
    if not mock_mode and config.get("summarizer", {}).get("enabled", True):
        summarizer = PaperSummarizer(config)
        summarizer.summarize(ranked)

    # 4. 存入数据库
    save_papers(date_label, ranked)
    email_papers = load_papers(date_label)
    html = build_email(email_papers, config["keywords"])

    # 4. 发送或预览
    if mock_mode or dry_run:
        save_html_preview(html, date_label)
    else:
        send_email(config, html)

    logger.info("Done — %d papers for %s", len(email_papers), date_label)


if __name__ == "__main__":
    main()
