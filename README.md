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

# 联网搜索无需配置，DuckDuckGo 免费、无需 API Key。
# 优先搜索以下官方数据源，确保结果权威性。
```

## 知识库

RAG 系统基于 ChromaDB（向量存储）+ SQLite FTS5（全文检索）双引擎，共约 57,000 条文档。

### 数据来源

| 来源 | 文档数 | 内容类型 | 说明 |
|------|--------|----------|------|
| 招生计划 | 37,661 | 各省院校招生专业/计划/学费 | 2025年公开数据 |
| 大学专业介绍 | 4,823 | 专业课程、就业方向、学科评估 | 百科级 |
| 张雪峰书籍/课程 | 4,258 | 志愿填报方法论和案例 | PDF 扫描 |
| 热门专业盘点 | 3,464 | 专业分析、行业趋势 | 机构出品 |
| 张雪峰志愿填报课程 | 2,158 | 直播转录稿、经验分享 | 视频转录 |
| 电子书与电子资料 | 1,701 | 志愿填报指南和高教资料 | PDF/电子书 |
| 2025 高考数据 | 659 | **批次线、一分一段表、分数位次对照** | 官方数据汇总 |
| 2026 招生政策 | 746 | 各省招生工作规定和高校章程 | 阳光高考网 |
| 志愿填报百科 | 542 | 志愿规则、退档规则、平行志愿 | 入门必需 |
| 全国各省一分一段表 | 134 | 历年各省分数-位次对照 | 历史数据 |
| 机构出品填报指南 | 390 | 112页专业填报手册 | 专业机构 |

> **数据总规模**：57,865 条文档。article 占 95%（方法论/规则/分析），live_transcript 占 4%（直播转录），score_data 占 1%（批次线和一分一段表）。score_data 在搜索中享有优先注入权，确保 LLM 获取精确位次数据。

### 数据采集

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

**注意：** 数据文件（`data/` 目录下的 ChromaDB pickle、SQLite、extracted 文本）不入 git 仓库，需要本地自行采集。采集脚本仅用于获取政府公开的高考教育数据，使用时应遵守目标网站的 robots.txt 并控制请求频率。

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
│   │   ├── hybrid_search.py#   混合搜索（向量+FTS5+注入+联网）
│   │   ├── vector_search.py#   向量检索
│   │   ├── keyword_search.py#   SQLite FTS5 检索
│   │   ├── web_search.py   #   联网搜索（DuckDuckGo）
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

## 回答策略

LLM 的推理核心是**志愿填报五步法**，贯穿在所有回答中：

```
1. 分数定位 → 分数不重要，位次才重要。从一分一段表精确查找，禁止估算
2. 专业筛选 → 兴趣排第二，就业排第一。看专业壁垒高低、行业基本面
3. 地域匹配 → 选城市比选学校名字重要。产业集群在哪，实习机会在哪
4. 院校定档 → 专业实力 > 综合排名。行业认可度 > 985/211 名头
5. 风险对冲 → 给自己留后路。转专业难易度、考研/考公兼容性、行业周期
```

五步法由 `src/utils/prompt_templates.py` 中的 `MAIN_SYSTEM_PROMPT` 定义，所有场景共享。不同场景（智能问答/志愿评估/观点检索）在此基础上叠加各自的 `SCENE_PROMPTS`。

---

用户提交问题后，系统经过完整流水线处理：

```
用户输入
  │
  ├── ① 安全检测 ─────────────→ 不通过 → 返回安全提醒，拒绝回答
  │                             通过 ↓
  ├── ② 意图路由 ─────────────→ volunteer / opinion / style_chat / general
  │     基于关键词预检 + LLM 二次确认，不同意图走不同 prompt 模板
  │
  ├── ③ 多路混合搜索 ─────────→ RRF 融合 + 联网兜底
  │     ├─ 向量检索（charbigram hash，语义兜底）
  │     ├─ FTS5 全文检索（SQLite 关键词匹配）
  │     ├─ 省份注入（扫描 ChromaDB 中 score_data 文档，匹配用户省份）
  │     └─ 联网搜索（优先14个官方数据源，本地不足时按需触发）
  │          │
  │     ┌────┴────┐
  │     │ RRF 融合 │ ← 三路结果加权合并，联网结果追加在末尾
  │     └────┬────┘
  │
  ├── ④ 位次精确提取 ─────────→ 从搜索结果中匹配一分一段表
  │     ├─ 找到精确位次 → 写入 prompt：用户N分 → 位次XXX名（禁止估算）
  │     └─ 未找到 → 标记「缺少精确一分一段表」
  │
  ├── ⑤ LLM 生成 ─────────────→ 主模型 → 失败时自动切换备用模型
  │     ├─ 智能问答：流式 SSE 返回，300-800 字/轮
  │     └─ 志愿评估：生成结构化 JSON（院校列表 + 位次 + 分析 + 风险）
  │
  ├── ⑥ 后端位次覆写 ─────────→ 无论 LLM 输出什么 rank 值，
  │                              后端用步骤④提取的精确值强制覆盖
  │
  ├── ⑦ 会话持久化 ───────────→ SQLite 存储
  │     ├─ 普通对话：role + content
  │     └─ 志愿评估：content_type=volunteer_assessment + structured_data
  │
  └── ⑧ 前端渲染 ─────────────→ 按 content_type 分发
        ├─ 普通文本 → Markdown 渲染
        └─ volunteer_assessment → 结构化卡片（位次定位 + 冲稳保 + 概率条 + 专业分析 + 风险提示）
```

### 各环节说明

| 环节 | 核心文件 | 说明 |
|------|----------|------|
| 安全检测 | `src/safety/input_gateway.py` | 拦截越狱/隐私/辱骂/地域攻击四类输入 |
| 意图路由 | `src/agent/router.py` | 高分+省份关键词直接判定 volunteer；其余走 LLM 分类 |
| 混合搜索 | `src/retrieval/hybrid_search.py` | 向量 + FTS5 + 省份注入 + 联网，RRF 融合后取 Top 10 |
| 联网搜索 | `src/retrieval/web_search.py` | DuckDuckGo 免费，优先搜 14 个官方数据源，本地不足时按需触发 |

**联网搜索优先数据源：**

| 类别 | 来源 | 域名 |
|------|------|------|
| 查分与政策 | 阳光高考网 | gaokao.chsi.com.cn |
| | 各省教育考试院 | bjeea.cn, sxkszx.cn 等 6 省 |
| 选校与专业 | 软科排名 | shanghairanking.cn |
| | 教育部学科评估 | cdgdc.edu.cn |
| | 青塔网 | cingta.com |
| 就读体验 | 哐哐大学 | kuangkuangdaxue.com |
| 高考综合 | 掌上高考 | eol.cn |
| | 高考100 | gk100.com |
| | 大学生必备网 | dxsbb.com |
| 位次提取 | `src/api/tools.py` 中的 `_extract_rank_from_results` | 正则匹配 `\| N分 \| 位次 \|` 格式的表数据 |
| LLM 生成 | `src/api/chat.py` 中的 `_call_llm` | 主模型优先，异常时自动切备用；prompt 模板在 `src/utils/prompt_templates.py` |
| 位次覆写 | `src/api/tools.py` 第 244-252 行 | `result["summary"]["rank"] = exact_rank`，绕过 LLM 估算偏差 |
| 会话持久化 | `src/knowledge/session_store.py` | `add_turn` 支持 dict 类型 `assistant_msg`，区分普通对话和结构化结果 |

### 志愿评估 vs 智能问答

| | 智能问答 | 志愿评估 |
|---|---|---|
| 触发方式 | 输入框自由提问 | 表单提交省份/分数/科类 |
| prompt 模板 | `volunteer`（对话式，300-800字） | `volunteer_form`（报告式，完整 JSON） |
| LLM 输出 | 流式文本 | 机构化 JSON（summary + schools + risks） |
| 位次定位 | 从上下文估算 | **精确查表 + 后端覆写** |
| 前端渲染 | Markdown | 卡片（冲/稳/保 + 概率条 + tier 筛选） |
| 会话历史 | 文本回放 | **卡片原样恢复** |

## 使用注意事项

1. **首次启动需要 API Key**。在 `.env` 或设置面板配置 DeepSeek API Key，否则 LLM 调用会返回「未配置」提示
2. **志愿评估必须有数据**。运行 `scrape_2026_admission.py` 采集一分一段表，否则 LLM 只能用批次线反推位次（误差大）
3. **一键清除乱码数据**：如果搜索结果质量差，运行 `python scripts/_clean_garbled.py` 清除低质量文档
4. **2025 数据单独索引**：采集新的 2025 年数据文件后，运行 `python scripts/_reindex_2025.py` 以 `score_data` 类型入库
5. **北京采用 3+3 模式**，不分物理/历史类。提交时选"物理类"不影响结果，后台自动处理
6. **所有建议不构成最终决策依据**，位次数据标注了年份来源，提醒用户到省教育考试院官网核实

## 后续迭代

### 下一版本（v2）

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | **官方数据爬虫** | 直接爬各省教育考试院一分一段表 + 青塔网学科评估。替代目前从二手网站采集，数据更权威、更全 |
| P0 | **全省份一分一段表** | 当前仅北京/山西有完整精确数据。补全 31 省 2025 年一分一段表，全部省份走精确查表 |
| P0 | **Claude 主模型** | 志愿评估切换到 Claude（ Anthropic API），位次引用遵循度远超 DeepSeek，无需后端覆写 |
| P1 | **院校 2025 录取数据** | 当前院校推荐用的是 2024 年录取分。补 2025 年录取最低分和位次 |
| P1 | **BM25 jieba 分词** | 当前 BM25 用的是字符 bigram，数字匹配弱。换成 jieba 分词后 "598分" 能精确命中 "598" |
| P1 | **院校对比** | 多选院校并排对比：分数、位次、专业、就业率、学费 |
| P2 | **ECharts 位次分布图** | 志愿评估报告中加可视化：位次分布条形图、录取概率雷达图 |
| P2 | **收藏 & 导出** | 收藏目标院校，导出 PDF 报告 |
| P2 | **移动端适配** | 响应式布局，手机上也能填表单看报告 |

### 更远期

- 就业数据接入（麦可思报告、招聘网站薪资数据）
- 校园真实评价聚合（哐哐大学、知乎、小红书）
- 性格/兴趣测评 → 专业推荐
- 多轮对话式志愿填报向导

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
