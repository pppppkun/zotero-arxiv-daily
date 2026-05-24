"""Flask Web 前端 — 浏览 arXiv Daily 论文历史数据。"""
import yaml
from flask import Flask, render_template, request

from store import get_available_dates, load as load_papers

app = Flask(__name__)


def _load_config():
    with open("config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@app.route("/")
def index():
    config = _load_config()
    dates = get_available_dates()
    selected = request.args.get("date", dates[0] if dates else "")
    papers = load_papers(selected) if selected else []
    return render_template(
        "index.html",
        dates=dates,
        selected=selected,
        papers=papers,
        keywords=config.get("keywords", []),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
