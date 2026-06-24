# 高考志愿AI助手

基于公开教育数据和 LLM 构建的**高考志愿填报智能评估系统**。输入省份、分数、意向专业，生成结构化志愿评估报告——含位次定位、冲/稳/保院校推荐、录取概率、专业就业分析和风险提示。

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue" alt="Python">
  <img src="https://img.shields.io/badge/framework-FastAPI-009688" alt="FastAPI">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

## 快速启动

```bash
# 1. 克隆仓库
git clone https://github.com/你的用户名/zhangxuefengagent.git
cd zhangxuefengagent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key

# 4. 采集2025年高考数据（首次使用必须运行）
python scripts/scrape_2026_admission.py

# 5. 启动服务
python app_api.py
```

浏览器打开 `http://localhost:7860`。

## 功能

| 功能 | 说明 |
|------|------|
| **智能问答** | 自由输入问题，LLM + 知识库检索回答 |
| **志愿评估** | 填写省份/分数/科类/意向，生成结构化评估报告 |
| **冲稳保推荐** | 三档院校推荐 + 录取概率条 + tier 筛选 |
| **位次定位** | 自动从一分一段表精确查找位次，禁止估算 |
| **会话历史** | 侧边栏保留所有对话和评估结果，点击可回溯 |
| **系统设置** | 面板配置主/备用模型 API Key 和端口 |

## 配置

编辑 `.env` 文件：

```bash
# 主模型（DeepSeek）
ZXF_LLM_PRIMARY_API_KEY=sk-你的key
ZXF_LLM_PRIMARY_MODEL=deepseek-v4-pro

# 备用模型（主模型失败时自动切换）
ZXF_LLM_FALLBACK_API_KEY=sk-你的key
ZXF_LLM_FALLBACK_MODEL=deepseek-chat

# 向量模型（语义搜索）
ZXF_EMBEDDING_API_KEY=sk-你的key
ZXF_EMBEDDING_MODE=api

# 服务端口
GRADIO_PORT=7860
```

## 数据采集

知识库依赖 ChromaDB 存储的文档和 SQLite 结构化数据。首次使用需要采集：

```bash
# 2025年高考招生政策和一分一段表
python scripts/scrape_2026_admission.py

# 视频转录（可选）
python scripts/transcribe_videos.py

# OCR扫描件（可选）
python scripts/ocr_scanned_pdfs.py

# 已有数据重新索引
python scripts/_reindex_2025.py
```

**注意：** 数据文件（`data/` 目录下的 ChromaDB pickle、SQLite、extracted 文本）不入 git 仓库，需要在本地自己采集。

## 项目结构

```
zhangxuefengagent/
├── app_api.py              # FastAPI 入口
├── Dockerfile              # Docker 构建（可选）
├── docker-compose.yml      # Docker Compose（可选）
├── requirements.txt        # Python 依赖
├── .env.example            # 配置模板
│
├── src/
│   ├── api/                # 接口层
│   │   ├── chat.py         #   SSE 流式对话
│   │   ├── tools.py        #   志愿评估 / 配置 CRUD
│   │   ├── conversations.py#   会话管理
│   │   ├── search.py       #   对话搜索
│   │   └── dependencies.py #   依赖注入（启动时初始化服务）
│   │
│   ├── agent/              # Agent 层
│   │   ├── volunteer.py    #   志愿评估处理
│   │   ├── opinion.py      #   观点检索
│   │   ├── style_chat.py   #   风格聊天
│   │   ├── fallback.py     #   通用兜底
│   │   └── router.py       #   意图路由
│   │
│   ├── retrieval/          # 检索层
│   │   ├── hybrid_search.py#   混合搜索（向量 + FTS5 + 注入）
│   │   ├── vector_search.py#   向量检索
│   │   ├── keyword_search.py#   SQLite FTS5 检索
│   │   ├── structured_query.py# 结构化 SQL 查询
│   │   ├── embedding_service.py# Embedding 服务
│   │   └── reranker.py     #   重排序
│   │
│   ├── knowledge/          # 知识存储层
│   │   ├── chroma_store.py #   ChromaDB（向量 + 倒排）
│   │   ├── sqlite_store.py #   SQLite FTS5
│   │   └── session_store.py#   会话持久化
│   │
│   ├── safety/             # 安全层
│   │   └── input_gateway.py#   输入安全检测
│   │
│   └── utils/              # 工具
│       ├── prompt_templates.py# Prompt 模板
│       ├── conversation.py    # 对话管理
│       └── logger.py          # 日志
│
├── static/                 # 前端
│   ├── index.html          #   SPA 页面
│   ├── css/style.css       #   样式
│   └── js/                 #   前端逻辑
│       ├── app.js          #     编排 & 志愿评估渲染
│       ├── chat.js         #     对话流
│       ├── sidebar.js      #     会话列表
│       ├── api.js          #     API 封装
│       ├── settings.js     #     设置面板
│       └── utils.js        #     工具函数
│
├── scripts/                # 数据采集 & 工具脚本
│   ├── scrape_2026_admission.py  # 爬招生政策
│   ├── extract_all.py            # 数据抽取
│   ├── index_mvp.py              # 索引构建
│   ├── _clean_garbled.py         # 乱码清理
│   └── _reindex_2025.py          # 2025数据重索引
│
└── data/                   # 本地数据（gitignore）
    ├── chroma_db/          #   ChromaDB pickle
    ├── gaokao.db           #   SQLite 数据库
    ├── extracted/          #   提取文本
    ├── raw/                #   原始文件
    └── processed/          #   处理后文件
```

## 架构

```
用户输入 → 安全检测 → 意图路由 → 混合搜索 → LLM 生成 → 结构化渲染
                                    │
                            ┌───────┼────────┐
                            ▼       ▼        ▼
                         向量检索  FTS5检索  省份注入
                            │       │        │
                            └───┬───┘────────┘
                                ▼
                          RRF 融合 → 重排序 → 返回
```

- **混合检索**：向量（语义）+ FTS5（全文）+ 省份关键词注入（精确命中一分一段表）
- **位次覆写**：后端从检索结果中提取一分一段表精确位次，直接覆写 LLM 返回的 `summary.rank`，避免 LLM 估算偏差
- **LLM 路由**：意图分类 → volunteer / opinion / style_chat / general，不同场景不同 prompt
- **会话持久化**：SQLite 存储，支持 `content_type` 区分普通对话和结构化评估结果

## 使用注意事项

1. **首次启动需要 API Key**。在 `.env` 或设置面板配置 DeepSeek API Key，否则 LLM 调用会返回「未配置」提示
2. **志愿评估必须有数据**。运行 `scrape_2026_admission.py` 采集一分一段表，否则 LLM 只能用批次线反推位次（误差大）
3. **一键清除乱码数据**：如果搜索结果质量差，运行 `python scripts/_clean_garbled.py` 清除低质量文档
4. **2025 数据单独索引**：采集新的 2025 年数据文件后，运行 `python scripts/_reindex_2025.py` 以 `score_data` 类型入库
5. **北京采用 3+3 模式**，不分物理/历史类。提交时选"物理类"不影响结果，后台自动处理
6. **所有建议不构成最终决策依据**，位次数据标注了年份来源，提醒用户到省教育考试院官网核实

## Docker（可选）

```bash
# 构建镜像
docker-compose build

# 启动
docker-compose up -d

# 数据、日志和模型挂载在 ./data ./logs ./models
```

## License

MIT
