"""Paper summarization via local vLLM model — downloads PDF, extracts text, generates summary."""
import logging
import time

import fitz  # PyMuPDF
import httpx

logger = logging.getLogger(__name__)


class PaperSummarizer:
    """Downloads paper PDFs, extracts text, and calls local vLLM for 3-4 sentence summaries."""

    def __init__(self, config: dict):
        sc = config.get("summarizer", {})
        self.top_n = sc.get("top_n", 20)
        self.max_pdf_chars = sc.get("max_pdf_chars", 10000)
        self.download_delay = sc.get("pdf", {}).get("download_delay", 3)

        vllm = sc.get("vllm", {})
        self.vllm_base = vllm.get("base_url", "http://localhost:8000/v1")
        self.vllm_model = vllm.get("model", "Qwen/Qwen3-4B")
        self.vllm_key = vllm.get("api_key", "not-needed")
        self.vllm_timeout = vllm.get("timeout", 120)

        self._http = httpx.Client(trust_env=False, timeout=self.vllm_timeout)

    def summarize(self, papers: list[dict]) -> list[dict]:
        """Summarize top_n papers in-place. Returns papers unchanged on failure."""
        to_summarize = papers[: self.top_n]

        for i, p in enumerate(to_summarize):
            if p.get("summary") is not None:
                continue

            title = p["title"]
            logger.info("[%d/%d] Summarizing: %s", i + 1, len(to_summarize), title[:80])

            try:
                pdf_bytes = self._download_pdf(p["url"])
                pdf_text = self._extract_text(pdf_bytes)
                summary = self._call_llm(p["title"], p["abstract"], pdf_text)
                p["summary"] = summary
                logger.info("  -> summary: %s", summary[:100])
            except Exception:
                logger.exception("Failed to summarize %s", p["id"])
                p["summary"] = None

            if i < len(to_summarize) - 1:
                time.sleep(self.download_delay)

        return papers

    def _download_pdf(self, arxiv_url: str) -> bytes:
        """Download PDF from arXiv. Converts abs URL to pdf URL."""
        pdf_url = arxiv_url.replace("/abs/", "/pdf/")
        r = self._http.get(pdf_url, follow_redirects=True)
        r.raise_for_status()
        return r.content

    def _extract_text(self, pdf_bytes: bytes) -> str:
        """Extract plain text from PDF bytes using PyMuPDF."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        text = "\n".join(pages)
        return text[: self.max_pdf_chars].strip()

    def _call_llm(self, title: str, abstract: str, pdf_text: str) -> str:
        """Send PDF text to vLLM for summarization via OpenAI-compatible API."""
        prompt = (
            "You are a research paper summarizer. Generate a concise summary of 3-4 sentences "
            "covering the main contribution, methodology, and key findings of the following paper.\n\n"
            f"Title: {title}\n"
            f"Abstract: {abstract}\n"
            f"Full text:\n{pdf_text}\n\n"
            "Summary:"
        )

        payload = {
            "model": self.vllm_model,
            "messages": [
                {"role": "system", "content": "You are a helpful research paper summarizer."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 300,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.vllm_key}",
        }

        r = self._http.post(
            f"{self.vllm_base}/chat/completions",
            json=payload,
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"].strip()
        return content or "Summary unavailable"
