import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "data" / "papers.db"


def _get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            date TEXT NOT NULL,
            arxiv_id TEXT NOT NULL,
            title TEXT,
            abstract TEXT,
            authors TEXT,
            categories TEXT,
            url TEXT,
            published TEXT,
            score REAL,
            summary TEXT,
            PRIMARY KEY (date, arxiv_id)
        )
    """)
    try:
        conn.execute("ALTER TABLE papers ADD COLUMN summary TEXT")
    except sqlite3.OperationalError:
        pass
    return conn


def save(date: str, papers: list[dict]) -> None:
    """保存某一天的论文列表，同一天重复运行覆盖旧数据。"""
    conn = _get_conn()
    with conn:
        conn.execute("DELETE FROM papers WHERE date = ?", (date,))
        rows = [
            (
                date,
                p["id"],
                p["title"],
                p["abstract"],
                json.dumps(p["authors"], ensure_ascii=False),
                ", ".join(p["categories"]),
                p["url"],
                p["published"],
                p["score"],
                p.get("summary"),
            )
            for p in papers
        ]
        conn.executemany(
            "INSERT INTO papers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
        )
    logger.info("Saved %d papers for %s", len(papers), date)


def load(date: str) -> list[dict]:
    """读取某一天的论文列表，按相似度降序。"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM papers WHERE date = ? ORDER BY score DESC",
        (date,),
    ).fetchall()
    conn.close()

    return [
        {
            "id": r[1],
            "title": r[2],
            "abstract": r[3],
            "authors": json.loads(r[4]),
            "categories": r[5].split(", "),
            "url": r[6],
            "published": r[7],
            "score": r[8],
            "summary": r[9],
        }
        for r in rows
    ]


def get_available_dates() -> list[str]:
    """返回所有有数据的日期，降序排列。"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT DISTINCT date FROM papers ORDER BY date DESC"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]
