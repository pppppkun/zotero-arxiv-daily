import logging
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class SimilarityEngine:
    """使用 sentence-transformers 计算关键词与论文的相似度。"""

    def __init__(self, model_name: str):
        logger.info("Loading model: %s", model_name)
        self.model = SentenceTransformer(model_name)

    def rank(self, papers: list[dict], keywords: list[str], top_n: int) -> list[dict]:
        """计算每篇论文与关键词的相似度，返回排序后的 top-N。"""
        if not papers:
            return []

        # 拼接论文文本
        paper_texts = [f"{p['title']} {p['abstract']}" for p in papers]

        # 批量编码
        logger.info("Encoding %d papers and %d keywords...", len(papers), len(keywords))
        paper_embeddings = self.model.encode(
            paper_texts,
            show_progress_bar=False,
            normalize_embeddings=False,
        )
        keyword_embeddings = self.model.encode(
            keywords,
            show_progress_bar=False,
            normalize_embeddings=False,
        )

        # 余弦相似度：先归一化再点积
        paper_norm = paper_embeddings / np.linalg.norm(paper_embeddings, axis=1, keepdims=True)
        keyword_norm = keyword_embeddings / np.linalg.norm(keyword_embeddings, axis=1, keepdims=True)
        similarity_matrix = paper_norm @ keyword_norm.T  # (papers, keywords)

        # 每篇论文取最高相似度
        scores = similarity_matrix.max(axis=1)

        # 按得分排序
        ranked = sorted(zip(papers, scores), key=lambda x: x[1], reverse=True)
        top_papers = ranked[:top_n]

        logger.info("Top-%d papers scored between %.4f and %.4f", top_n,
                     top_papers[-1][1], top_papers[0][1])

        # 附加得分到论文
        result = []
        for paper, score in top_papers:
            paper["score"] = round(float(score), 4)
            result.append(paper)
        return result
