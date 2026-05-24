# arXiv Daily

每日自动拉取 arXiv 最新论文，基于关键词相似度排序，支持 LLM 摘要生成，并通过邮件推送精选内容。

## 功能

- **论文抓取** — 从 arXiv API 按分类（cs.AI, cs.SE 等）拉取指定日期的论文
- **语义排序** — 使用 sentence-transformers 计算论文与关键词的相似度，按相关性排序
- **PDF 摘要** — 通过本地 vLLM 模型对论文 PDF 自动生成 3-4 句摘要
- **邮件推送** — 将排序后的论文生成 HTML 邮件，每日发送
- **Web 浏览** — Flask Web 界面浏览历史论文数据

## 项目结构

```
arxiv-daily/
├── main.py          # 主入口，串联抓取、排序、摘要、邮件流程
├── fetcher.py       # arXiv API 论文抓取（httpx + Atom XML 解析）
├── similarity.py    # 语义相似度计算与排序
├── summarizer.py    # PDF 下载 + vLLM 摘要生成
├── mailer.py        # HTML 邮件生成与 SMTP 发送
├── store.py         # JSON 文件存储
├── web.py           # Flask Web 前端
├── mock_data.py     # 测试用模拟数据
├── config.yaml      # 配置文件（含凭据，已 gitignore）
└── templates/       # HTML 模板（邮件 + Web 页面）
```

## 快速开始

### 依赖

- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) 包管理器

```bash
uv sync
```

### 配置

复制并编辑配置文件：

```bash
cp config.yaml.example config.yaml
```

主要配置项：

- `arxiv.categories` — 关注的 arXiv 分类
- `arxiv.max_results_per_category` — 每个分类拉取论文数上限
- `keywords` — 用于匹配论文的关键词列表
- `similarity.model_name` — sentence-transformers 模型
- `ranker.top_n` — 最终保留的论文数
- `email.*` — SMTP 邮件配置
- `summarizer.enabled` — 是否启用 LLM 摘要
- `summarizer.vllm.base_url` — vLLM 推理服务地址

### 运行

```bash
# 正式运行
uv run python main.py

# 指定日期
uv run python main.py --date 2026-05-20

# 模拟运行（使用样本数据，不发邮件）
uv run python main.py --mock

# 试运行（真实抓取，预览邮件，不发送）
uv run python main.py --dry-run
```

### Web 界面

```bash
uv run python web.py
```

浏览器访问 `http://localhost:8080`，可按日期浏览历史论文。

## 工作流程

1. **Fetch** — 按分类从 arXiv API 拉取论文元数据（标题、摘要、作者等）
2. **Rank** — 将论文标题+摘要编码为向量，与关键词向量做余弦相似度排序
3. **Summarize** — 对 Top-N 论文下载 PDF，调用本地 vLLM 模型生成摘要
4. **Store** — 结果存入 `data/` 目录下的 JSON 文件
5. **Mail** — 生成 HTML 邮件并通过 SMTP 发送

## License

MIT
