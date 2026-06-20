# 张雪峰知识蒸馏 Agent — 项目方案

> 版本: v1.0 | 日期: 2026-06-20 | 状态: 设计阶段

---

## 目录

1. [项目概述](#1-项目概述)
2. [核心设计理念](#2-核心设计理念)
3. [数据源规划](#3-数据源规划)
4. [系统架构](#4-系统架构)
5. [思维层设计](#5-思维层设计)
6. [佐证层设计](#6-佐证层设计)
7. [语料层与 RAG 管线](#7-语料层与-rag-管线)
8. [Agent 路由器与场景处理器](#8-agent-路由器与场景处理器)
9. [检索策略](#9-检索策略)
10. [容错与降级机制](#10-容错与降级机制)
11. [日志与可观测性](#11-日志与可观测性)
12. [Gradio UI 设计](#12-gradio-ui-设计)
13. [部署方案](#13-部署方案)
14. [技术选型总结](#14-技术选型总结)
15. [分阶段实施路线图](#15-分阶段实施路线图)
16. [可行性评估](#16-可行性评估)

---

## 1. 项目概述

### 1.1 项目目标

构建一个以张雪峰老师知识体系为核心的 **全能型知识蒸馏 Agent**，覆盖以下四大场景：

- **高考/考研志愿建议**：输入分数、省份、兴趣方向，给出院校和专业建议
- **观点检索与总结**：检索并总结张雪峰对特定专业/行业/现象的看法
- **风格化对话**：以张雪峰的语言风格和决策逻辑与用户互动
- **趋势分析**：结合实时就业数据辅助教育决策

### 1.2 交付形态

Web 应用（Gradio），浏览器直接访问，供家长、考生等非技术用户使用。

### 1.3 项目目录结构

```
D:/zhangxuefengagent/
├── app.py                  # Gradio 主入口
├── config.py               # 全局配置
├── requirements.txt        # Python 依赖
├── Dockerfile              # Docker 镜像
├── docker-compose.yml      # 容器编排
├── data/
│   ├── raw/                # 原始素材 (视频/音频/网页)
│   ├── processed/          # 清洗后的文本
│   └── chroma_db/          # ChromaDB 持久化数据
├── models/                 # 本地模型文件 (BGE, Reranker)
├── logs/                   # 日志目录
│   ├── app.log
│   ├── error.log
│   └── health.json
├── src/
│   ├── __init__.py
│   ├── data/               # 数据采集与预处理
│   │   ├── crawler.py      # 网页爬取
│   │   ├── transcriber.py  # 视频转录 (Whisper)
│   │   ├── cleaner.py      # 文本清洗
│   │   └── splitter.py     # 自定义文本切片器
│   ├── knowledge/          # 知识层
│   │   ├── chroma_store.py # ChromaDB 向量库管理
│   │   ├── sqlite_store.py # SQLite 结构化 + FTS5
│   │   └── schema.sql      # 佐证层表结构 DDL
│   ├── agent/              # Agent 层
│   │   ├── router.py       # 意图路由器
│   │   ├── volunteer.py    # 志愿建议处理器
│   │   ├── opinion.py      # 观点检索处理器
│   │   ├── style_chat.py   # 风格聊天处理器
│   │   └── fallback.py     # 通用兜底处理器
│   ├── retrieval/          # 检索管线
│   │   ├── hybrid_search.py    # 混合检索调度
│   │   ├── vector_search.py    # ChromaDB 向量检索
│   │   ├── keyword_search.py   # SQLite FTS5 关键词检索
│   │   ├── structured_query.py # 佐证层结构化查询
│   │   └── reranker.py         # BGE-Reranker 重排序
│   └── utils/
│       ├── logger.py       # 日志与健康检查
│       ├── prompt_templates.py # System Prompt 模板
│       └── health.py       # 服务健康状态管理
└── tests/                  # 测试目录
```

---
## 2. 核心设计理念

### 2.1 双层蒸馏架构

Agent 的核心设计哲学：**蒸馏的是"张雪峰怎么想"，而不是"张雪峰说过什么"。**

三层各司其职：
- **思维层** 定调子（张雪峰的判断框架 + 语言风格）
- **佐证层** 给数据（可独立更新的结构化事实）
- **语料层** 提供原文依据（"张老师在某次直播里确实讲过这个"）


## 2. 核心设计理念

### 2.1 双层蒸馏架构

Agent 的核心设计哲学：蒸馏的是张雪峰怎么想，而不是张雪峰说过什么。

三层各司其职：
- **思维层** 定调子（张雪峰的判断框架 + 语言风格）
- **佐证层** 给数据（可独立更新的结构化事实）
- **语料层** 提供原文依据

### 2.2 张雪峰决策框架（五步决策链）



### 2.3 思维层工程化方式

| 方式 | 内容 | 作用 |
|------|------|------|
| **System Prompt** | 将5步决策链写入 system prompt | 保证思维结构一致 |
| **Few-shot Examples** | 精选20-30条经典连麦对话 | 校准表达风格 |
| **约束规则集** | 硬编码边界条件（如不推荐无壁垒专业的底线） | 防止矛盾结论 |

---

## 3. 数据源规划

### 3.1 数据源全景

**第一梯队：核心内容（直接产出）**

| 类型 | 来源 | 形态 | 难度 |
|------|------|------|:---:|
| 直播连线切片 | 抖音/快手/B站 张雪峰老师账号 | 短视频 3-10分钟 | 中等 |
| 长直播回放 | B站/抖音完整直播录屏 | 长视频 1-3小时 | 较高 |
| 出版书籍 | 考研/高考志愿相关书籍 | 结构化文字 | 低 |
| 付费课程 | 志愿填报/考研规划课程 | 视频+课件 | 高(版权) |

**第二梯队：延伸内容（间接产出）**

| 类型 | 来源 | 形态 | 难度 |
|------|------|------|:---:|
| 综艺/访谈 | 奇葩说/演说家/鲁豫有约等 | 视频/文字稿 | 中等 |
| 演讲实录 | 高校演讲/教育论坛 | 视频/文字 | 中等 |
| 社交媒体 | 张雪峰微博/公众号推文 | 短文/长文 | 低 |
| 新闻采访 | 媒体专访/热点回应 | 文字 | 低 |

**第三梯队：衍生与佐证**

| 类型 | 来源 | 价值 |
|------|------|------|
| 讨论/解读 | 知乎/小红书高赞内容 | 多角度补充 |
| 数据佐证 | 教育部目录/就业报告/录取分数线 | 事实基线 |
| 实时就业趋势 | BOSS直聘/猎聘/36氪/发改委等 | 动态趋势判断 |

### 3.2 分阶段采集策略

- Phase 1 (MVP): 社交媒体文章 + 精选50-100条高价值切片转录 + 人工整理15-20条核心就业趋势
- Phase 2 (深度): 批量爬取更多短视频 + 综艺/访谈文字稿 + 知乎高赞讨论
- Phase 3 (增强): 教育部/就业结构化数据 + 自动爬虫 + 用户反馈回流

---

## 4. 系统架构

### 4.1 三层架构总览

     数据层              知识层             智能层            展示层
   (Data)           (Knowledge)         (Agent)         (Presentation)

  视频转录
  网页爬取  ──→  文本切片 ──→ ChromaDB 向量库 ──→ 混合检索 ──→ Gradio
  文档解析        Embedding    SQLite FTS5         Reranker       Web UI
  就业数据  ──→ 结构化存储 → SQLite 关系表 ──→ 精确查询

### 4.2 数据流详解

      原始素材
         |
    ┌────┼────┐
    ▼         ▼
  结构化     非结构化
   (佐证)     (语料)
    |         |
    ▼         ▼
  SQLite   文本切片 → Embedding → ChromaDB
  关系表      |
    |      SQLite FTS5 (关键词索引)
    |         |
    └────┬────┘
         ▼
    混合检索调度
    (向量 + 关键词 + 结构化)
         |
         ▼
      Reranker
         |
         ▼
     LLM 推理生成
         |
         ▼
    Gradio 响应

---

## 5. 思维层设计

### 5.1 张雪峰决策框架（五步决策链）

```
用户输入：考生分数 + 省份 + 意向方向
              |
      ┌───────▼────────┐
      | 1. 分数定位       |  « 位次 > 分数，本省竞争格局
      └───────┬────────┘
              ▼
      ┌───────▼────────┐
      | 2. 专业筛选       |  « 就业第一，兴趣第二；专业壁垒高低
      └───────┬────────┘
              ▼
      ┌───────▼────────┐
      | 3. 地域匹配       |  « 产业集群在哪，实习机会密度
      └───────┬────────┘
              ▼
      ┌───────▼────────┐
      | 4. 院校定档       |  « 专业实力 > 综合排名，行业认可度
      └───────┬────────┘
              ▼
      ┌───────▼────────┐
      | 5. 风险对冲       |  « 转专业/考研/考公兼容性，行业周期
      └───────┬────────┘
              ▼
         最终建议输出
```

### 5.2 工程化落地方式

| 方式 | 内容 | 作用 |
|------|------|------|
| System Prompt | 将5步决策链写入 system prompt | 保证思维结构一致 |
| Few-shot Examples | 精选20-30条经典连麦对话 | 校准表达风格和判断倾向 |
| 约束规则集 | 硬编码边界条件 | 防止与张雪峰立场矛盾的结论 |

### 5.3 Few-shot 示例格式

```json
{
  "user": "老师，孩子理科600分，四川，想学医，有什么推荐？",
  "context": {"省份": "四川", "科类": "理科", "分数": 600, "意向": "医学"},
  "response": "600分在四川...首先你要搞清楚，医学是个大类，临床和口腔是两条路，分数差别很大。其次你要看你想在哪就业..."
}
```

---

## 6. 佐证层设计

### 6.1 核心表结构

佐证层使用 SQLite 存储所有结构化事实数据，走精确 SQL 查询，不进向量库。

**院校信息表 (universities)**
- id, name, province, city, tier (985/211/双一流/普通), type (综合/理工/师范/医学), is_public

**录取分数线表 (admission_scores)** — 佐证层核心
- university_id, province, year, category (理科/文科/综合改革), batch, min_score, min_rank, major
- 索引: (university_id, year), (province, year, category)

**专业目录表 (majors)**
- code (教育部专业代码), name, category, sub_category, barrier_level (专业壁垒: 高/中/低)

**就业趋势表 (employment_trends)**
- major, major_id, industry, trend (上升/持平/下行), confidence (0-1), signal_count, signals (JSON), avg_salary, demand_ratio, source, period
- 索引: (major_id), (trend)

**城市产业集群表 (city_industries)**
- city, province, cluster (互联网/半导体/汽车/金融), scale, major_companies

**专业-院校映射表 (major_university)**
- major_id, university_id, ranking_grade (学科评估等级 A+/A/A-/B+), is_key_major

### 6.2 就业趋势数据更新机制

```
定时爬虫(每周) + RSS推送(实时) + 手动录入(按需)
              │
              ▼
        数据验证与去重
              │
              ▼
        SQLite UPSERT 入库
              │
              ▼
        置信度自动衰减 (超过3个月未更新: confidence 自动从 0.8 降至 0.5)
```

### 6.3 结构化数据使用示例

```
用户: "河南理科580分计算机推荐什么学校"

第1步 - SQL 精确查询:
  SELECT * FROM admission_scores
   WHERE province='河南' AND category='理科'
   AND year=2025 AND major LIKE '%计算机%'
   AND min_score BETWEEN 560 AND 600

第2步 - 就业趋势匹配:
  SELECT * FROM employment_trends
   WHERE major IN ('计算机科学与技术','软件工程','人工智能')

第3步 - 城市产业匹配:
  SELECT * FROM city_industries
   WHERE cluster IN ('互联网','IT','软件')
   → 结合候选院校所在地，标注产业配套
```

---

## 7. 语料层与 RAG 管线

### 7.1 离线索引管线

```
原始素材 -> 文本提取 -> 智能切片 -> Embedding -> ChromaDB 入库

视频 --> Whisper 转录 ---+
网页 --> trafilatura ------+--> 文本清洗 -> 语义切片 -> BGE-M3 Embedding
文档 --> Unstructured ----+               (按话题/问答对切分)

佐证数据(结构化) ---> SQLite -----> 直接查询，不进向量库
就业趋势数据   ---> 结构化存储 -> 直接查询，不进向量库
```

### 7.2 在线查询管线

```
用户问题 -> 意图识别(Router) -> 查询改写 -> 多路召回 -> 重排序 -> LLM

查询改写:
  - 子查询分解 (复杂问题拆分)
  - 回溯查询 (升维检索方法论层)
  - 直接查询 (简单问题/兜底)

多路召回:
  +--- 向量检索 (ChromaDB, 语义匹配)
  +--- 关键词检索 (SQLite FTS5, 精确匹配)
  +--- 结构化查询 (SQLite 关系表, 佐证层)

融合: RRF (Reciprocal Rank Fusion)
```

### 7.3 文本切片策略

封装 ZhangXuefengTextSplitter，按内容类型使用不同策略：

| 内容类型 | 主分隔符 | chunk_size | 特殊规则 |
|---------|---------|:---:|------|
| 直播连麦 | QA边界 (问：/答：/家长：) | 800 | Q和A必须在同一chunk |
| 社交媒体 | 帖子边界 (---/===) | 1500 | 一篇帖子一个chunk |
| 长文/访谈 | 标题层级 (##/###) | 600 | 按章节边界 |
| 书籍章节 | 章/节标记 | 1000 | 按章节边界 |
| 结构化数据 | — | — | 不切分，直接存SQLite |

### 7.4 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 文本提取 | Whisper + trafilatura + Unstructured | Python 成熟组合 |
| Embedding | BGE-M3 (本地或API) | 中文效果最优，支持稠密+稀疏混合 |
| 向量库 | ChromaDB | 轻量，Python原生，单机足够 |
| 关键词检索 | SQLite FTS5 + jieba 分词 | 零依赖，与佐证层复用同一数据库 |
| 重排序 | BGE-Reranker-v2-m3 | 中文最佳性价比，568M参数 |

### 7.5 数据规模评估

| 内容类型 | 预估总量 | 文本量 |
|---------|---------|--------|
| 短视频切片 | ~1000条 | ~50万字 |
| 长直播回放 | ~200场 | ~300万字 |
| 社交媒体 | ~1000篇 | ~100万字 |
| 书籍 | ~5本 | ~80万字 |
| 访谈/演讲 | ~100个 | ~50万字 |
| 第三方讨论 | ~500条 | ~30万字 |
| **合计** | | **~600万字，约1.5-2万chunk** |

检索性能：ChromaDB < 50ms，FTS5 < 5ms，总存储 < 500MB

---


## 8. Agent 路由器与场景处理器

Test content for section 8.

---

### 8.1 路由器设计

用户只面对一个对话入口，系统自动分发到对应场景处理器。

```
用户输入
    |
    v
意图分类器 (Router)
    |
    +--> 志愿建议 Agent (volunteer)
    +--> 观点检索 Agent (opinion)
    +--> 风格聊天 Agent (style_chat)
    +--> 通用兜底 (fallback)
```

意图分类通过 LLM few-shot 实现，无需单独模型。

### 8.2 四个场景处理器的差异化策略

| 场景 | 检索策略 | 佐证层 | 风格 |
|------|---------|:---:|------|
| 志愿建议 | 子查询分解+回溯查询 (分数->位次->院校->专业) | 全开 | 务实直接，数据驱动 |
| 观点检索 | 直接查询+回溯查询 | 仅就业趋势 | 忠实原文，引述风格 |
| 风格聊天 | 不检索/轻检索 | 不使用 | 张雪峰风格，幽默扎心 |
| 通用兜底 | 直接查询 | 按需 | 默认助人 |

### 8.3 通用兜底策略

当用户问题与教育/升学/就业无关时，不是冷冰冰拒绝，而是用张雪峰人设自然化解：

- 完全无关问题 -> 张雪峰式幽默拒绝 + 引导回正题
- 边界模糊的教育问题 -> 轻量检索 + 思维层做有限推理
- 能合理延展的问题 -> 从就业角度拉回框架

示例：
- 用户问天气 -> "天气好不好你打开窗户看一眼不就知道了...咱还是聊点正经的，你孩子高考那点事想清楚了吗？"
- 用户问辞职信 -> "辞职这事儿我管不了，但你辞职之后打算干什么、靠什么吃饭——这个我能跟你好好聊聊。"

### 8.4 意图分类实现

```python
ROUTER_PROMPT = """判断用户意图，输出 JSON：
{"scene": "volunteer"|"opinion"|"style_chat"|"general", "confidence": 0.0-1.0}

volunteer: 涉及高考志愿、分数、选专业、选学校、考研择校
opinion: 询问张雪峰对某个专业/行业/现象的看法
style_chat: 闲聊、心态、人生建议类（不带具体志愿参数）
general: 以上都不是或不好判断
"""
```

---

## 9. 检索策略

### 9.1 四种检索策略

| 策略 | 保留 | 优先级 | 说明 |
|------|:---:|:---:|------|
| 直接查询 | YES | P0 | 基准线，兜底 |
| 子查询分解 | YES | P0 | 复杂问题必须拆 |
| 回溯查询 | YES | P1 | 抓张雪峰方法论层知识，价值高 |
| HyDE | No | P2 | 多一次LLM调用，中文对话场景收益不明显 |

### 9.2 回溯查询的价值

张雪峰的很多回答是先讲原则再给结论。回溯查询先抽象一步：

```
用户问："土木工程还值得学吗"
  -> 直接检索 -> "土木工程 还值得学吗"
  -> 回溯查询 -> "张雪峰关于行业下行周期专业的通用判断原则"
     命中 -> "看一个专业不能只看现在火不火，要看四个维度：
             1.行业基本面有没有结构性变化
             2.你能不能考上更好的替代专业
             3.这个专业的下限在哪
             4.你愿不愿意读研换方向"
```

### 9.3 检索流程

```
用户问题
    |
    v
意图识别
    |
    +-- 简单问题 --> 直接查询
    +-- 复杂问题 --> 子查询分解 + 回溯查询(升维)
    |
    v
多路并行检索
    +-- 向量检索 (ChromaDB, HNSW): 语义匹配
    +-- 关键词检索 (SQLite FTS5 + jieba): 精确匹配
    +-- 结构化查询 (SQLite): 佐证层数据
    |
    v
RRF融合 -> Reranker (BGE-v2-m3) -> Top-K 送 LLM
```

---

## 10. 容错与降级机制

### 10.1 故障点全景

```
用户请求
    |
    v
意图分类  --故障②: LLM超时/乱输出--> 降级: 走通用兜底
    |
    v
查询改写  --故障①: 子查询/回溯失败--> 降级: 直接查询
    |
    v
多路检索
  +-- 向量检索 --故障③: ChromaDB挂了--> 跳过，仅用FTS5
  +-- 关键词检索 --故障④: SQLite锁--> 重试100ms
  +-- 结构化查询 --故障⑤: 全空--> LLM诚实推断
    |
    v
重排序 --故障⑥: Reranker异常--> 降级: 原始分排序
    |
    v
LLM生成 --故障⑦: API挂了--> 备用模型--> 检索原文兜底
    |
    v
响应
```

### 10.2 各故障点处理策略

| 故障点 | 策略 | 用户感知 |
|--------|------|:---:|
| 查询改写失败 | 降级直接查询 | 基本无感 |
| 意图分类失败 | 降级通用兜底 | 风格略有差异 |
| ChromaDB挂了 | 仅靠FTS5+SQLite | 语义检索缺失 |
| SQLite异常 | 重试+跳过 | 基本无感 |
| 全部检索为空 | LLM诚实推断 | 诚实告知信息不足 |
| Reranker异常 | 原始分排序 | 排序略差 |
| LLM API挂了 | 备用模型->检索原文 | 有感知但不崩溃 |

### 10.3 核心原则

**系统可以降级，但不能崩溃。用户面对的永远是一个能给出回复的界面。**

### 10.4 LLM 最终兜底

```
抱歉，现在我这边脑子转不动了。不过我把最相关的几段张老师的原话贴给你，
你先看看有没有帮助：

1. [检索到的 Top-3 语料原文]
2. ...
3. ...

这是我目前能找到的最相关内容，等我恢复了你再来问。
```

---

## 11. 日志与可观测性

### 11.1 日志分级

| 级别 | 含义 | 内容 |
|------|------|------|
| ERROR | 服务挂了，用户可能有感知 | 错误详情+traceback+修复建议 |
| WARNING | 降级/兜底触发，用户基本无感 | 降级动作+原因 |
| INFO | 正常流程节点 | 检索耗时、命中数量、意图分类结果 |
| DEBUG | 开发调试用 | 全量检索原文、LLM原始返回 |

### 11.2 单条日志结构

```json
{
  "timestamp": "2026-06-20T15:32:01.123",
  "level": "WARNING",
  "component": "chromadb",
  "event": "vector_search_failed",
  "detail": {
    "error": "Connection refused",
    "fallback_action": "skipped_vector_search_use_fts5_only",
    "user_query": "河南理科580分计算机推荐什么学校",
    "scene": "volunteer",
    "duration_ms": 1200,
    "retry_count": 1
  },
  "session_id": "sess_abc123",
  "trace_id": "trace_xyz789"
}
```

### 11.3 日志文件结构

```
logs/
├── app.log              # 当日全量日志
├── app.log.2026-06-19   # 按天轮转，保留30天
├── error.log            # 仅ERROR级别，快速排查
└── health.json          # 实时服务健康状态
```

### 11.4 health.json（供UI面板自查）

```json
{
  "updated_at": "2026-06-20T15:32:01",
  "services": {
    "chromadb":    {"status": "healthy", "last_error": null},
    "sqlite":      {"status": "healthy", "last_error": null},
    "llm_primary": {"status": "healthy", "last_error": null},
    "llm_fallback":{"status": "healthy", "last_error": null},
    "embedding":   {"status": "healthy", "last_error": null},
    "reranker":    {"status": "degraded", "last_error": "Connection timeout at 15:28"}
  },
  "recent_errors": [
    {
      "time": "2026-06-20T15:28:05",
      "component": "reranker",
      "error": "Connection timeout after 3000ms",
      "action_taken": "降级为原始检索分排序",
      "fix_suggestion": "检查reranker服务是否启动，执行 docker compose up -d reranker"
    }
  ]
}
```

### 11.5 用户可见的三种检查方式

| 方式 | 路径 | 场景 |
|------|------|------|
| Gradio UI 健康面板 | 页面顶部状态栏 | 日常瞄一眼 |
| /health 命令 | 对话中输入 | 详细报告 |
| logs/health.json | 文件系统 | 排查问题查原始数据 |

### 11.6 日志工具类核心能力

- 根据故障类型自动生成修复建议（如："ChromaDB未启动，执行 docker compose up -d chromadb"）
- 同步更新 health.json 供UI面板消费
- 生成人类可读健康报告（/health命令输出）
- 最近20条错误保留，按时间倒序

---

## 12. Gradio UI 设计

### 12.1 页面布局

四个 Tab 页：
- 智能问答：主聊天界面，自动路由到对应场景处理器
- 志愿评估：结构化表单（省份/分数/科类/兴趣方向），填写后生成志愿建议报告
- 语录搜索：关键词搜索 + 语义搜索张雪峰语录，按话题/时间/来源筛选
- 知识库管理（后台）：上传新素材、查看索引状态、管理佐证数据

### 12.2 智能问答 Tab

- ChatInterface 组件，支持流式输出
- 顶部服务状态条（chips 组件）：各服务健康指示器
- 点击状态条展开错误详情和修复建议
- 输入 `/health` 查看完整健康报告
- 输入 `/sources` 查看当前回答引用的原始语料

### 12.3 志愿评估 Tab

- 表单字段：省份（下拉）、科类（理科/文科/综合改革）、分数、位次（可选）、意向专业方向（多选）、意向城市（多选）
- 提交后流式生成评估报告：
  1. 分数定位分析
  2. 院校推荐（冲刺/稳妥/保底三档）
  3. 专业匹配度分析
  4. 就业前景评估
  5. 风险提示

### 12.4 语录搜索 Tab

- 搜索框 + 筛选器（话题标签、时间范围、内容类型）
- 结果展示：原文片段 + 来源标注（如"2024.03 抖音直播连线"）
- 点击展开完整上下文

---

## 13. 部署方案

### 13.1 Docker 单容器部署（推荐 MVP）

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 7860
CMD ["python", "app.py"]
```

```yaml
# docker-compose.yml
services:
  zhangxuefeng:
    build: .
    ports:
      - "7860:7860"
    volumes:
      - ./data:/app/data
      - ./models:/app/models
      - ./logs:/app/logs
    environment:
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_BASE_URL=${LLM_BASE_URL}
      - EMBEDDING_API_KEY=${EMBEDDING_API_KEY}
```

一条命令启动：`docker compose up -d`

### 13.2 容器内组件

```
Docker Container
├── Gradio UI :7860
├── FastAPI :8000 (可选，API层)
├── ChromaDB (in-process，嵌入Python进程)
├── SQLite (文件，volume持久化)
├── RAG Pipeline
└── Embedding/Reranker (本地模型或API调用)
```

### 13.3 扩展方案（Phase 2+）

当数据量增长后，可将 ChromaDB 拆为独立服务：

```yaml
services:
  chromadb:
    image: chromadb/chroma:latest
    ports: ["8001:8000"]
    volumes:
      - ./chroma_data:/chroma/chroma
  app:
    build: .
    ports: ["7860:7860"]
    environment:
      - CHROMA_HOST=chromadb
    depends_on: [chromadb]
```

### 13.4 各组件 Docker 化

| 组件 | Docker 方式 | 备注 |
|------|------------|------|
| SQLite | 不需要镜像，文件挂载 | 嵌入式 |
| ChromaDB | In-process 或 chromadb/chroma 镜像 | 小规模用 in-process |
| Gradio | 打包进 Python 镜像 | EXPOSE 7860 |
| Whisper | 打包进基础镜像 | 首次启动下载模型 |
| jieba | 打包进基础镜像 | 纯Python |
| BGE-M3/Reranker | 本地模型挂载或API | GPU版换 cuda 基础镜像 |

---

## 14. 技术选型总结

### 14.1 核心技术栈

| 层级 | 组件 | 选型 | 说明 |
|------|------|------|------|
| 前端 | Web UI | Gradio 4.x | ChatInterface + Tab |
| Agent 层 | LLM | Claude API / DeepSeek | 主备双模型 |
| RAG 框架 | 编排 | LangChain | RetrievalQA + Chain |
| 向量库 | Embedding 存储 | ChromaDB | In-process, 单机 |
| Embedding | 文本向量化 | BGE-M3 | 中文最优 |
| 关键词检索 | 全文索引 | SQLite FTS5 + jieba | 零运维 |
| 结构化存储 | 关系数据 | SQLite | 佐证层 + 语料FTS5 |
| 重排序 | 结果精排 | BGE-Reranker-v2-m3 | 568M参数 |
| 视频转录 | 语音转文字 | Whisper | OpenAI 开源模型 |
| 文本提取 | 网页/文档解析 | trafilatura + Unstructured | |
| 中文分词 | 关键词索引 | jieba | |
| 部署 | 容器化 | Docker + Docker Compose | 单容器 MVP |

### 14.2 方案对比

| 方案 | 开发爽度 | 运维爽度 | 适合场景 |
|------|:---:|:---:|------|
| SQLite + ChromaDB (当前) | 10/10 | 10/10 | 个人/小团队，百万级数据 |
| PG + pgvector | 8/10 | 7/10 | 需要一个独立DB服务时 |
| MySQL + Milvus | 5/10 | 2/10 | 十亿级向量，分布式 |
| LanceDB + SQLite | 9/10 | 10/10 | ChromaDB 替代，格式更开放 |
| Elasticsearch | 7/10 | 4/10 | 功能全但太重 |

### 14.3 Reranker 选型

| 模型 | MTEB | 参数量 | 推荐场景 |
|------|:---:|:---:|------|
| BGE-Reranker-v2-m3 | 67.3 | 568M | **推荐**，有GPU本地，无GPU调API |
| Qwen3-Reranker-0.6B | 68.1 | 600M | 备选 |
| BGE-Reranker-v2-minicpm | >70 | 2.4B | 效果好但太重，不推荐 |
| Qwen3-Reranker-4B | >72 | 4B | 太重，2万条数据不需要 |

---

## 15. 分阶段实施路线图

### Phase 1 — MVP（2-3 周）

**目标：** 跑通核心链路，能用

| 模块 | 内容 | 工期 |
|------|------|:---:|
| 项目骨架 | 目录结构、配置、Dockerfile、docker-compose | 1天 |
| 数据采集 | 爬取公众号/微博文章 + 精选50条切片转录 | 3天 |
| 知识库搭建 | SQLite建表 + ChromaDB索引管线 + 文本切片器 | 2天 |
| 佐证层初始化 | 人工整理15-20条核心就业趋势 + 分数线样例 | 2天 |
| Agent 核心 | 路由器 + 4个场景处理器 + System Prompt | 3天 |
| 检索管线 | 混合检索 + Reranker + 容错降级 | 2天 |
| Gradio UI | ChatInterface + 健康状态栏 + 志愿评估表单 | 2天 |
| 日志系统 | AgentLogger + health.json + /health命令 | 1天 |
| 联调测试 | 端到端测试 20+ 典型用户问题 | 2天 |

### Phase 2 — 深度覆盖（3-4 周）

**目标：** 语料丰富度达到可用水平

| 模块 | 内容 |
|------|------|
| 批量数据采集 | 200+ 切片转录 + 综艺访谈文字稿 + 知乎高赞 |
| 佐证层扩展 | 自动爬虫（36氪/猎聘报告）+ 分数线批量导入 |
| 多轮对话 | 对话历史管理 + 上下文感知检索 |
| Few-shot 优化 | 50+ 精标注示例对 |
| 用户反馈 | 点赞/踩 + 反馈收集 + 知识纠错入口 |
| 性能优化 | 检索缓存 + 预加载 embedding |

### Phase 3 — 增强与扩展（长期）

| 模块 | 内容 |
|------|------|
| 知识图谱 | 专业-院校-就业-城市的轻量图索引 |
| 多模态 | 支持用户上传成绩单截图 OCR 识别 |
| 用户系统 | 历史记录、收藏、个性化设置 |
| 数据分析 | 用户提问热力图、高频话题分析 |
| 通知推送 | 分数线更新、就业趋势异动提醒 |
| 移动端 | 小程序或 PWA 封装 |

---

## 16. 可行性评估

### 16.1 技术可行性

| 维度 | 评估 | 说明 |
|------|:---:|------|
| 核心链路 | ✅ 可行 | RAG + LLM 是成熟范式，无技术瓶颈 |
| 中文检索 | ✅ 可行 | BGE-M3 中文效果已验证，混合检索互补 |
| 数据采集 | ⚠️ 需注意 | 视频平台反爬、版权边界需关注 |
| 实时就业数据 | ⚠️ 需维护 | 数据源稳定性不确定，需降级方案 |
| 规模上限 | ✅ 充裕 | 预估 2 万 chunk，单机远远够用 |
| 部署运维 | ✅ 简单 | 单容器 Docker，一条命令启动 |

### 16.2 资源需求

| 资源 | MVP 阶段 | 生产环境 |
|------|---------|---------|
| 服务器 | 本地开发机即可 | 4C8G 云服务器（约 200 元/月） |
| GPU | 不需（Embedding/Reranker 调API） | 可选（本地部署 BGE 模型需 RTX 3060+） |
| 存储 | < 10GB | < 50GB（含所有原始素材） |
| LLM API | 约 100-300 元/月 | 约 500-1000 元/月（按日活 100 用户估算） |
| 开发人力 | 1 人 × 6-8 周（MVP） | 1 人长期维护 |

### 16.3 风险清单

| 风险 | 概率 | 影响 | 应对 |
|------|:---:|:---:|------|
| 张雪峰内容版权争议 | 中 | 高 | 仅使用公开内容，明确标注来源，必要时获取授权 |
| LLM API 不稳定 | 中 | 中 | 主备双模型，最终兜底返回检索原文 |
| 就业数据时效性 | 高 | 低 | 置信度自动衰减 + 用户明确告知数据日期 |
| 志愿建议法律责任 | 低 | 高 | 明确免责声明："仅供参考，不构成最终决策依据" |
| 用户期望过高 | 高 | 中 | 首次使用时展示能力边界说明 |
| 数据采集被限流/封禁 | 中 | 中 | 合理频率 + 手动采集兜底 |

### 16.4 核心风险应对细节

**版权与合规：**
- 所有语料标注来源（平台、日期、原链接）
- System Prompt 引导 Agent 引用时主动标注出处
- 不为付费课程内容做转录（版权墙不可逾越）
- 开源代码，语料数据不公开（仅提供索引工具）

**免责声明（强制展示）：**
> "本 Agent 基于张雪峰老师公开言论和第三方数据构建，旨在提供教育决策参考。
> 所有建议不构成最终决策依据，志愿填报请以各省教育考试院官方信息为准。"

### 16.5 结论

**项目可行，建议启动 Phase 1 MVP 开发。**

核心优势：
- 技术选型轻量务实，无过度工程
- 数据规模可控，单机轻松承载
- 降级策略完善，不依赖单一服务
- 分阶段交付，MVP 2-3 周可见成果

需要关注：
- 内容版权边界需要持续关注
- 佐证层数据的持续更新机制是长期壁垒
- 用户需明确理解 Agent 的能力边界

---

> 文档版本: v1.0
> 创建日期: 2026-06-20
> 作者: Claude Code + 用户协作
> 状态: 设计阶段完成，待进入实施规划


## 附录：内容安全与合规层

### A.1 架构位置

```
用户输入
    │
    ▼
┌──────────────────┐
│ 1. 输入安全网关    │  <- 第一道防线
│  敏感词 + 意图检测  │
└────┬─────────────┘
     │ 安全
     ▼
┌──────────────────┐
│ 2. 意图路由 + 检索  │  <- 原有流程
└────┬─────────────┘
     │
     ▼
┌──────────────────┐
│ 3. 输出安全审核    │  <- 第二道防线
│  生成内容合规检查   │
└────┬─────────────┘
     │ 安全
     ▼
   用户响应
```

### A.2 不合规场景分类与处理

| 类别 | 用户query示例 | 风险 | 处理策略 |
|------|-------------|:---:|------|
| 政治敏感 | 涉及领导人、体制攻击、分裂言论 | 🔴 | 直接拒绝，模板化回复 |
| 地域攻击 | "XX地方的人是不是都不行" | 🟡 | 拒绝+纠偏引导 |
| 专业歧视 | "学XX专业的都是废物" | 🟡 | 框架化纠正+引导 |
| 人身攻击 | 辱骂张雪峰或其他人 | 🟡 | 轻幽默化解+引导 |
| 越狱/注入 | "忽略之前的指令..." | 🔴 | 直接拒绝，不暴露prompt |
| 虚假信息 | "张雪峰说XXX大学明年取消所有专业" | 🟡 | 标注"未找到相关表述" |
| 恶意诱导 | "帮我骂XX大学招生办" | 🟡 | 拒绝+引导建设性方向 |
| 隐私窥探 | "张雪峰家住哪/手机号" | 🔴 | 直接拒绝，保护隐私 |

### A.3 输入安全网关

三层递进过滤：硬规则(~1ms) -> 关键词匹配 -> LLM安全分类(~500ms)

硬规则正则（零延迟直接拦截）：
- 越狱注入：忽略/忘记/覆盖 + 指令/prompt/规则/人格
- 政治红线：特定政治敏感词（视部署场景调整）
- 隐私窥探：隐私/手机号/家庭地址 + 张雪峰

LLM安全分类（模糊边界时调用）：
- 分类标签：normal / political / regional_attack / jailbreak / privacy / abuse
- 正常讨论教育、就业、专业、院校选择是合规的

### A.4 输出安全审核

双层审核策略：
- 规则快速扫描（~1ms）：检查是否包含政治敏感词、歧视性表述
- LLM深度审核：仅对规则无法判定或高风险的回复进行，采样率10%

### A.5 分层拒绝策略

| 风险 | 回复策略 | 示例 |
|:---:|------|------|
| 🔴 高危 | 模板化拒绝 | "抱歉，我无法回答。我是教育规划和志愿填报助手，请聊聊升学就业相关话题。" |
| 🟡 中危 | 框架化引导 | 地域攻击 -> "每个省份都有独特的产业集群和就业机会，来看看你的分数在你省的水平？" |
| 🟢 合规 | 正常流程 | |

### A.6 免责声明

> 本Agent基于张雪峰老师公开言论和第三方数据构建，旨在提供教育决策参考。
> 所有建议不构成最终决策依据，志愿填报请以各省教育考试院官方信息为准。
> Agent输出的观点不代表张雪峰老师本人立场。

### A.7 性能优化

- 硬规则+关键词覆盖90%+违规case，零延迟
- LLM安全分类仅消耗在模糊边界case上
- 输出审核采样率10%，正常回复不逐个审核
- 外部内容安全API暂不接入（Phase 2评估是否需要）

---

## 附录 B：设计补全 — P0 缺口

### B.1 新高考适配

#### 背景

29 省已推行新高考，选科组合直接决定可报专业范围。原设计中理科/文科二分法已不适用。

#### 佐证层表结构扩展

```sql
-- 新增：选科要求映射表
CREATE TABLE major_selection_requirements (
    id              INTEGER PRIMARY KEY,
    major_id        INTEGER REFERENCES majors(id),
    province        TEXT NOT NULL,
    year            INTEGER NOT NULL,
    required_subjects TEXT,              -- 必选科目，如 "物理" 或 "物理,化学"
    optional_subjects TEXT,              -- 任选其一，如 "化学,生物,地理"
    selection_count INTEGER DEFAULT 1,   -- 需从optional中选几门
    source          TEXT,                -- 省教育考试院官方文件
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 扩展 admission_scores 表
ALTER TABLE admission_scores ADD COLUMN selection_combo TEXT;
-- 如 "物化生" / "物化地" / "史地政" 等选科组合
-- 同一院校同一专业在不同选科组合下可能有不同分数线
```

#### 决策链调整

```
原：省份 + 科类(理/文) + 分数     → 院校推荐
新：省份 + 选科组合 + 分数         → 可报专业范围 → 院校推荐
       │
       ├→ 选科组合 = "物理,化学,生物"
       │   → 可报：绝大多数理工科 + 部分医学
       │   → 不可报：不提物理要求的文科专业
       │
       ├→ 选科组合 = "历史,地理,政治"
       │   → 可报：大多数文科 + 不提科目要求的专业
       │   → 不可报：要求物理/化学/生物的理工科
       │
       └→ 选科组合 = "物理,地理,政治"
           → 可报：部分理工科 + 文理兼收专业
```

#### 新增系统 Prompt 规则

```
当用户提问不含选科信息时：
1. 如果是新高考省份用户，主动询问选科组合
2. 推荐专业时，标注每个专业的选科要求
3. 如用户选科无法覆盖某专业方向，明确告知
```


### B.2 多轮对话上下文管理

#### 用户典型行为

实际使用极少是单轮，而是连续追问：

```
用户: 河南理科580分计算机推荐什么学校
Agent: ...推荐了郑大、河大、西安邮电...
用户: 郑大和西安邮电比呢         (指代消解)
Agent: ...对比分析...
用户: 那我选计算机的话以后好考研吗 (话题漂移)
Agent: ...考研分析...
用户: 我刚才说的分数够不够郑大的软件工程 (回溯引用)
```

#### 设计

```python
class ConversationManager:
    """
    滑动窗口 + 摘要压缩 的混合策略
    
    近3轮: 完整保留 (滑动窗口)
    3-10轮: LLM 摘要压缩 (保留关键信息: 分数/省份/选科/意向专业)
    10轮+: 丢弃，仅保留摘要
    """
    
    def __init__(self, max_window=3, max_history=10):
        self.messages = []          # 完整消息
        self.context_state = {      # 始终维护的结构化状态
            "province": None,       # 省份
            "score": None,          # 分数
            "subject_combo": None,  # 选科组合
            "interests": [],        # 意向专业
            "key_facts": [],        # LLM 提取的关键事实
        }
    
    def add_turn(self, user_msg: str, agent_msg: str):
        self.messages.append({"role": "user", "content": user_msg})
        self.messages.append({"role": "assistant", "content": agent_msg})
        self._update_context_state(user_msg, agent_msg)
    
    def get_context_for_llm(self) -> str:
        """构造送给LLM的上下文"""
        recent = self.messages[-6:]  # 最近3轮
        summary = self._summarize_older()  # 更早的摘要
        state = json.dumps(self.context_state, ensure_ascii=False)
        return f"对话状态:\n{state}\n\n历史摘要:\n{summary}\n\n最近对话:\n{recent}"
```

#### 上下文状态维护策略

| 信息类型 | 维护方式 | 示例 |
|---------|---------|------|
| 省份/分数/选科 | 首次提取后持久保留，用户更新时覆盖 | "我是河南的" -> context_state.province = "河南" |
| 已推荐过的院校 | 追加到列表，去重 | 避免重复推荐 |
| 用户偏好倾向 | LLM 每轮自动判断并更新 | "我想留省内" -> preference = "省内优先" |
| 话题变化 | 检测到话题切换时标记 | 从"选校"切换到"考研" |

#### 指代消解

```
用户: "郑大和西安邮电比呢"
  -> 上下文中有上一轮推荐的院校列表 [郑大, 河大, 西安邮电]
  -> 消解: 对比 郑州大学 vs 西安邮电大学
```

实现方式：在 query 送入检索前，用 LLM 做一次轻量指代消解，将"它""那个""刚才说的"替换为具体实体名。

---

### B.3 RAG 质量评估框架

#### 为什么必须有

没有评估就不知道改 prompt、调 chunk 策略、换 embedding 模型到底是变好了还是变差了。

#### 评估维度

| 维度 | 指标 | 方法 |
|------|------|------|
| 检索质量 | Recall@5, MRR, NDCG@5 | 自动化跑分 |
| 回答质量 | 准确性、完整性、风格一致性 | LLM-as-Judge + 人工抽检 |
| 引用准确 | 引用来源是否真实存在 | 自动化验证 |
| 安全合规 | 违规回复率 | 安全网关统计 |

#### Golden Dataset 构建

```python
# tests/golden_dataset.json
[
  {
    "query": "河南理科580分计算机推荐什么学校",
    "expected_scene": "volunteer",
    "expected_sources": ["doc_123", "doc_456"],
    "expected_key_points": ["位次比分数重要", "计算机看好城市"],
    "forbidden_content": ["xx大学2024分数线xxx"] # 不应出现的幻觉事实
  },
  # ... 初期目标 50 条，覆盖 4 个场景
]
```

#### 自动化评估流程

```
每次代码/数据变更后:
  1. 跑 Golden Dataset 全量 query
  2. 对比 expected_scene vs 实际路由 -> 路由准确率
  3. 对比 expected_sources vs 实际召回 -> Recall@5
  4. 对召回结果计算 MRR, NDCG
  5. LLM-as-Judge 打分 (准确性 1-5, 风格 1-5)
  6. 生成评估报告 -> 对比上次基线
```

#### LLM-as-Judge 评分卡

```
用另一个独立的 LLM (不与 agent 共用同一个) 对回答评分:

1. 事实准确性 (1-5): 是否存在幻觉或编造数据
2. 框架一致性 (1-5): 是否遵循张雪峰五步决策逻辑
3. 风格匹配度 (1-5): 语言风格是否像张雪峰
4. 引用可信度 (1-5): 引用的来源和数据是否真实可查

总分 < 15 / 20 -> 标记为需要人工抽查
```

#### 目录扩展

```
D:/zhangxuefengagent/
└── tests/
    ├── golden_dataset.json     # Golden Dataset (50条+)
    ├── eval_runner.py          # 评估执行脚本
    ├── eval_baseline.json      # 上次评估基线
    └── eval_report.html        # 评估可视化报告
```

---

---

## 附录 C：设计补全 — P1 缺口

### C.1 特殊招生路径

张雪峰连麦中高频出现的问题类型，占实际录取约 20%。

#### 需覆盖的路径

| 路径 | 核心逻辑 | 佐证层需求 |
|------|---------|-----------|
| 强基计划 | 基础学科拔尖 + 本硕博连读，锁定专业 | 各校强基专业目录 + 入围分数线 |
| 综合评价 | 高考成绩 + 校测 + 学业水平 | 各校综评政策 + 往年入围条件 |
| 三大专项 | 国家/地方/高校专项，面向农村/贫困地区 | 实施区域列表 + 降分幅度 |
| 军校/警校 | 提前批，体检+政审 | 体检标准 + 政审要求 + 分数线 |
| 艺术/体育类 | 专业统考+文化课双上线 | 统考分数线 + 综合分计算公式 |

#### 实现方式

```
场景路由增加标签: volunteer -> special_admission

当用户提到以上关键词（强基/综评/专项/军校/艺考）:
  1. 路由到 volunteer 场景，但激活 special_admission 子流程
  2. 先检索该路径的政策规则（佐证层）
  3. 如果佐证层没有该政策的详细数据 -> 诚实告知 + 引导去省考试院官网查询
  4. System Prompt 追加对应场景的约束规则
```

### C.2 观点时间敏感性

#### 问题

张雪峰 2022 年说土木工程还不错 vs 2025 年说土木工程要慎重 —— 同一专业不同时期的判断可能相反。当前设计把语料混在一起检索，无法区分时间。

#### 设计

```json
// 每个 chunk 的 metadata 增加时间字段
{
  "content": "...",
  "metadata": {
    "source": "B站直播",
    "date": "2024-03-15",
    "source_url": "https://...",
    "topic": "计算机专业",
    "stance": "推荐",
    "conditions": "要看城市和具体方向"
  }
}
```

#### 检索时的时间加权

```python
def time_aware_rerank(chunks, current_date="2026-06-20"):
    for chunk in chunks:
        age_days = (current_date - chunk["date"]).days
        # 1年内: 1.0 / 1-2年: 0.8 / 2-3年: 0.6 / 3年+: 0.4
        chunk["time_weight"] = max(0.4, 1.0 - 0.2 * (age_days / 365))
        chunk["final_score"] = chunk["similarity"] * 0.7 + chunk["time_weight"] * 0.3
    return sorted(chunks, key=lambda c: c["final_score"], reverse=True)
```

#### System Prompt 时间感知指令

```
当引用张雪峰的观点时:
- 优先使用近1年的观点
- 如果引用了较旧的观点（超过2年），需标注时间
- 如果同一话题有前后矛盾的多条语料，选择最新的并提及差异
```

### C.3 增量索引策略

#### 问题

新增 50 条切片后，是追加还是重建整个 ChromaDB 索引？

#### 设计

ChromaDB 原生支持 add() 增量追加，不需要全量重建。

```sql
-- SQLite 索引追踪表
CREATE TABLE indexing_log (
    id              INTEGER PRIMARY KEY,
    source_file     TEXT NOT NULL,        -- 原始文件路径
    source_hash     TEXT NOT NULL,        -- 文件内容哈希（检测变更）
    content_type    TEXT NOT NULL,        -- 内容类型
    chunk_count     INTEGER,             -- 产生了多少个chunk
    chroma_ids      TEXT,                -- ChromaDB 中的 chunk ID 列表 (JSON)
    status          TEXT DEFAULT 'pending', -- pending/processing/done/failed
    error_message   TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX idx_source_hash ON indexing_log(source_hash);
```

#### 增量索引流程

```
新素材到达
    |
    v
计算 source_hash
    |
    +-> 已存在且 unchanged -> 跳过，不重复索引
    +-> 已存在但 changed   -> 删除旧 chunk，重新索引
    +-> 不存在              -> 新增索引
    |
    v
文本切片 -> Embedding -> ChromaDB.add() (增量追加)
    |
    v
更新 indexing_log
```

#### 全量重建触发条件
- Embedding 模型更换（BGE-M3 -> 其他模型）
- 切片策略重大变更（chunk_size 改变）
- 数据质量问题需要清洗后重做


### C.4 流式输出

#### 问题

Gradio ChatInterface 原生支持 streaming，设计文档未提及。LLM 调用 3-5 秒，如果等全部生成完再返回，用户感知很慢。

#### 设计

```python
# Gradio 原生支持 generator yield
def respond_streaming(message, history):
    # 1. 安全网关 (同步，~1ms)
    safety = input_safety_gateway.check(message)
    if not safety["safe"]:
        yield safety["reject_message"]
        return
    
    # 2. 意图路由 + 检索 (异步，~500ms)
    scene = router.classify(message)
    retrieved = hybrid_search.search(message, scene)
    
    # 3. 构造 prompt
    prompt = build_prompt(message, retrieved, scene)
    
    # 4. 流式生成 (边生成边返回)
    response = ""
    for chunk in llm.stream(prompt):
        response += chunk
        yield response  # Gradio 实时更新聊天框
```

#### 流式输出下的容错

```
如果流式生成到一半 LLM 挂了:
  -> 已输出的内容保留在聊天框
  -> 追加: "[生成中断，请稍后重试]"
  -> 后台自动重试
```

### C.5 回复引用标注

#### 问题

Agent 的回答目前没有标注信息来源，用户无法判断是张雪峰的真实观点还是 LLM 的推断。

#### 设计

```python
# System Prompt 中加入引用规则
CITATION_RULE = """
当你使用语料库中的张雪峰原话或观点时，在回答末尾附加引用标注：

格式：
---
参考来源:
[1] 2024.03.15 B站直播连线 - 张雪峰谈计算机专业选择
[2] 2025.01.10 公众号文章 - 关于土木工程行业变化的看法

如果观点来自你的推理而非语料，不需标注。
如果佐证层数据被使用，也标注:
[数据] 2025年河南省理科一本线数据 (来源: 河南省教育考试院)
"""
```

#### 前端展示

Gradio 中引用块使用折叠组件，默认收起，点击展开：

```
Agent: 计算机专业依然是值得推荐的方向，但要注意...

[展开查看 3 条参考来源 ▼]
  [1] 2024.03.15 B站直播 | 张雪峰连线河南家长
  [2] 2025.06 公众号 | 计算机行业就业趋势分析
  [3] 2025年河南省理科录取分数线数据
```

---

---

## 附录 D：P2 待办项（Phase 2+ 处理）

以下项目已识别但优先级较低，在 Phase 2 或之后处理：

| # | 项目 | 简要方案 |
|:---:|------|------|
| 1 | **首次使用引导** | 首次打开时弹出引导气泡，展示 5 个示例问题 + 能力边界说明 |
| 2 | **用户反馈闭环** | 每个回答下方 [有帮助] [没帮助] 按钮 + 可选文字反馈，存入 feedback 表供后续优化 |
| 3 | **结果导出/分享** | 一键复制为格式化文本或生成分享图片 |
| 4 | **成本监控** | 记录每次 LLM/Embedding API 调用的 token 消耗，仪表盘展示日/周/月费用 |
| 5 | **数据备份策略** | 每日凌晨 cron 打包 SQLite + ChromaDB 到 backup/ 目录，保留最近 7 天 |
| 6 | **知识库版本快照** | 重大更新前 git tag + ChromaDB snapshot |
| 7 | **并发限流** | 单用户每秒最多 2 个请求，全局并发上限 10，超过返回 "请稍后再试" |
| 8 | **Prompt 版本管理** | prompts/ 目录用 git 管理，文件名含版本号 (v1/v2)，eval 跑分后确定上线版本 |
| 9 | **语料语义去重** | 索引前对相邻 chunk 计算余弦相似度，>0.95 视为重复自动去重 |
| 10 | **考研择校场景** | Phase 2 独立设计，五步决策链需重构（院校层次>专业排名>导师>城市） |
| 11 | **专业横向对比** | 用户问 "A专业 vs B专业" 时，自动检索两个专业的壁垒/就业/薪资结构化数据做对比表 |
| 12 | **复读决策** | 增加复读场景，决策因素：分数提升空间/心理承受力/政策变化风险/家庭经济 |
| 13 | **张雪峰边界意识** | System Prompt 明确：如果某个专业张雪峰确实很少谈及，Agent 直接说这块我不太了解 |

---

---

## 附录 E：设计补全 — 剩余 P0 缺口

### E.1 System Prompt 完整模板

#### 主 System Prompt

```
你是张雪峰知识蒸馏 Agent。你的知识体系基于张雪峰老师公开言论、
教育行业数据和实时就业趋势构建。

## 核心身份
你以张雪峰老师的决策框架和语言风格来回答教育规划问题。
你不是复读机 —— 你用张雪峰的方法论做推理，而非单纯复述他的原话。

## 决策框架
面对用户问题时，按以下五步逻辑推理：

1. 分数定位 —— 分数不重要，位次才重要。先搞清楚用户在本省的水平
2. 专业筛选 —— 兴趣排第二，就业排第一。看专业壁垒高低、行业基本面
3. 地域匹配 —— 选城市比选学校名字重要。产业集群在哪，实习机会在哪
4. 院校定档 —— 专业实力 > 综合排名。行业认可度 > 985/211 名头
5. 风险对冲 —— 给自己留后路。转专业难易度、考研/考公兼容性、行业周期

每一步推理都要有依据：语料库中张雪峰的观点，或佐证层的客观数据。

## 语言风格
- 直接、务实、不绕弯子
- 用口语化表达，不写论文腔
- 适当使用张雪峰式的比喻和金句
- 该扎心的时候扎心，但出发点是为用户好

## 数据使用规则
- 佐证层的分数线、就业数据要明确标注年份和来源
- 引用张雪峰观点时，如果来自语料库，标注来源（时间+平台）
- 如果是基于框架的推理而非语料原文，说"我的判断是...依据是..."
- 遇到不确定的领域，诚实说"这块我了解得不够，不敢乱说"

## 安全边界
- 不涉及政治、地域攻击、人身攻击
- 不传播未经证实的政策变化或院校信息
- 所有建议不构成最终决策依据，引导用户查官方渠道核实
- 保护张雪峰老师和任何个人的隐私信息

## 回答结构（志愿建议场景）
1. 先快速定位（1-2句话总结用户情况）
2. 给出核心建议（2-3点，最重要放前面）
3. 展开分析（按五步框架）
4. 风险提示
5. 引用来源
```

#### 场景专用 Prompt 片段（动态拼接）

```python
SCENE_PROMPTS = {
    "volunteer": """
## 志愿建议场景
- 严格按照五步决策链推理
- 必须调用佐证层数据（分数线、就业趋势）
- 给出冲刺/稳妥/保底三档建议
- 明确标注任何数据推测 vs 确定数据
""",
    "opinion": """
## 观点检索场景
- 优先引用语料库中最相关的张雪峰原话
- 标注观点的时间，区分新旧观点
- 如果观点有前后变化，说明演变过程
- 不要把你的推理当作张雪峰的观点
""",
    "style_chat": """
## 风格聊天场景
- 放松数据引用要求，重点在语言风格
- 保持幽默、直接、接地气
- 即使闲聊也要传递正向的教育观
- 适时引导回教育规划主题
""",
    "general": """
## 通用场景
- 先用张雪峰风格回应，然后自然引导回教育话题
- 如果不属于任何教育相关领域，幽默化解后引导回正题
""",
}
```

### E.2 Few-shot 示例规格

#### 覆盖矩阵

目标：30 条示例，覆盖所有场景和常见话题：

| 场景 | 话题 | 数量 | 说明 |
|------|------|:---:|------|
| volunteer | 计算机/互联网类 | 4 | 热门方向 |
| volunteer | 医学类 | 3 | 临床/口腔/护理 |
| volunteer | 金融/经管类 | 2 | 财经院校选择 |
| volunteer | 师范/教育类 | 2 | 公费师范生 |
| volunteer | 土木/建筑类 | 2 | 下行行业如何处理 |
| volunteer | 文理兼收类 | 2 | 法学/新闻/外语 |
| volunteer | 新高考选科咨询 | 3 | 不同选科组合的路径 |
| opinion | 专业前景看法 | 3 | 各行业趋势判断 |
| opinion | 考研vs就业 | 2 | 学历价值讨论 |
| style_chat | 心态/焦虑 | 3 | 家长和考生常见心态 |
| style_chat | 人生选择 | 2 | 求学以外的话题 |
| general | 边缘/无关问题 | 2 | 兜底示范 |
| | **合计** | **30** | |

#### 示例规范

```json
{
  "id": "fewshot_001",
  "scene": "volunteer",
  "topic": "计算机专业选择",
  "user": "老师，孩子理科600分，四川，想学计算机，有什么推荐？",
  "context": {
    "province": "四川",
    "score": 600,
    "rank": "约15000名",
    "interest": "计算机类",
    "subject_combo": "物理+化学+生物"
  },
  "retrieved_sources": [
    {"id": "doc_123", "title": "2024.03 B站直播-张雪峰谈川渝计算机院校"},
    {"id": "doc_456", "title": "2025.01 公众号-计算机就业趋势"}
  ],
  "evidence_data": {
    "电子科技大学_计算机_2025_四川_理科": "最低录取位次约3000名",
    "四川大学_计算机_2025_四川_理科": "最低录取位次约5000名",
    "重庆邮电大学_计算机_2025_四川_理科": "最低录取位次约18000名"
  },
  "expected_response": "600分在四川理科...先看位次，你这个分大概在全省一万五左右..."
}
```

#### 质量控制

- 每条示例至少 2 人审阅（一人写，一人校验）
- 校验标准：事实准确、框架一致、风格匹配
- 每 3 个月根据新语料和用户反馈更新一轮

### E.3 测试策略

#### 测试金字塔

```
         /\
        /E2E\          3-5 条核心流程
       /------\
      /集成测试 \       10-15 个模块间接口
     /----------\
    /  单元测试   \     30-50 个核心函数
   /--------------\
  /  Golden Dataset \  50 条自动评估（已有）
 /------------------\
```

#### 单元测试

```python
# 覆盖以下模块的核心函数

tests/
├── test_splitter.py        # 文本切片：各内容类型切分边界
│   ├── test_qa_boundary_preserved()     # QA对不被切断
│   ├── test_chapter_boundary()          # 章节边界识别
│   └── test_overlong_chunk_fallback()   # 超长段降级切分
├── test_router.py          # 意图路由
│   ├── test_volunteer_classification()  # 志愿场景命中
│   ├── test_opinion_classification()    # 观点场景命中
│   ├── test_style_chat_classification() # 聊天场景命中
│   └── test_fallback_on_ambiguous()     # 模糊输入走兜底
├── test_hybrid_search.py   # 混合检索
│   ├── test_vector_search_returns_results()
│   ├── test_keyword_search_chinese()
│   ├── test_rrf_fusion()
│   └── test_empty_result_handling()
├── test_safety_gateway.py  # 安全网关
│   ├── test_hard_block_jailbreak()
│   ├── test_hard_block_political()
│   ├── test_pass_normal_education_query()
│   └── test_boundary_case()
├── test_conversation.py    # 对话管理
│   ├── test_window_sliding()
│   ├── test_context_state_update()
│   └── test_reference_resolution()
└── test_sqlite_store.py    # SQLite 操作
    ├── test_fts5_search()
    ├── test_admission_query()
    └── test_upsert()
```

#### 集成测试

| 测试 | 覆盖 |
|------|------|
| 完整 RAG 管线 | 输入 query -> 路由 -> 检索 -> 生成 -> 含引用的完整响应 |
| 多路召回融合 | 验证向量+关键词+结构化三路结果正确合并 |
| 容错降级链路 | 模拟 ChromaDB 挂 -> 验证自动切 FTS5 |
| LLM 主备切换 | 模拟主模型超时 -> 验证切备用模型 |
| 会话持久化 | 多轮对话 -> 关闭 -> 重新打开 -> 验证上下文恢复 |

#### E2E 测试

| 场景 | 覆盖 |
|------|------|
| 志愿建议完整流程 | 用户输入分数省份 -> 流式返回 -> 含引用 -> 追问 |
| 安全拦截 | 输入违规内容 -> 返回拒绝 -> 引导 |
| 错误降级 | 模拟 LLM 全挂 -> 返回检索原文兜底 |

#### 运行方式

```bash
# 每次 commit 前
pytest tests/ -m "not slow"   # 快速验证，< 30s

# 每次数据变更后
python tests/eval_runner.py   # 跑 Golden Dataset 全量

# 发版前
pytest tests/ -m "e2e"        # E2E 完整流程
```

### E.4 Embedding 部署决策

#### 决策树

```
是否需要离线可用？
  ├── 是 → 本地部署 BGE-M3
  │       需要 GPU (RTX 3060+, 6GB+ VRAM)
  │       首次加载 ~30s，推理 ~20ms/条
  │       2万条数据批量索引 ~7分钟
  │
  └── 否 → 优先 API
           ├── 硅基流动 BGE-M3 API: 中文效果一致，延迟 ~100ms
           │   价格: 约 0.001元/千tokens
           │   2万条索引: 约 2-5元
           │
           └── 备选: 阿里云 DashScope / 智谱 Embedding API
```

#### Phase 1 推荐：API 优先

```
理由:
- MVP 阶段先跑通，不想在 GPU 环境上花时间
- API 延迟 100ms vs 本地 20ms —— 对整体响应时间影响 < 5%
  （LLM 调用占了 3-5秒，embedding 差异可以忽略）
- 成本极低，每月几块钱
- Docker 镜像更小（不需要装 PyTorch + 模型文件）
```

#### 切换判断

```
满足以下任一条件时切换到本地部署:
- 月 API 调用费超过 100 元
- 需要离线/内网部署
- 对延迟有极致要求（< 50ms 端到端）
- 隐私合规要求数据不出服务器
```

#### Docker 适配

```dockerfile
# API 模式 (Phase 1, 默认)
FROM python:3.11-slim
# 不装 PyTorch，镜像约 300MB

# 本地模式 (Phase 2+, 按需切换)
FROM nvidia/cuda:12.1-runtime
RUN pip install FlagEmbedding
# 镜像约 3GB，需要 GPU
```

#### 实现层抽象

```python
class EmbeddingService:
    """统一接口，屏蔽 API vs 本地的差异"""
    
    def __init__(self, mode="api"):
        if mode == "api":
            self.backend = SiliconFlowEmbedding(
                model="BAAI/bge-m3",
                api_key=config.EMBEDDING_API_KEY
            )
        elif mode == "local":
            self.backend = LocalBGEMModel(
                model_path="models/bge-m3",
                device="cuda" if torch.cuda.is_available() else "cpu"
            )
    
    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.backend.encode(texts)
    
    def embed_query(self, text: str) -> list[float]:
        return self.backend.encode_query(text)
```

---

---

## 附录 F：设计补全 — 剩余 P1 缺口

### F.1 考研择校场景框架

#### 与高考决策链的核心差异

| 维度 | 高考 | 考研 |
|------|------|------|
| 分数机制 | 统考，全省统一分数线 | 初试+复试，各校自主划线 |
| 决策逻辑 | 分数->院校层次->专业 | 专业方向->导师/实验室->院校 |
| 信息透明度 | 录取分数线公开 | 复试线、报录比、导师信息碎片化 |
| 地域因素 | 产业集群优先 | 目标就业城市优先 |
| 风险结构 | 平行志愿兜底 | 调剂是唯一的兜底 |

#### 考研五步决策链

```
用户输入：本科院校+专业+目标方向+（可选：目标城市）
              |
      ┌───────▼────────┐
      | 1. 专业方向定级   |  <- 考本专业 / 跨考 / 相近专业
      |   跨考难度评估     |     难度：本专业 < 相近 < 跨大类
      └───────┬────────┘
              ▼
      ┌───────▼────────┐
      | 2. 院校层次匹配   |  <- 学科评估 > 985/211
      |   A+/A/B+ 学科   |     参考第四轮/第五轮学科评估
      └───────┬────────┘
              ▼
      ┌───────▼────────┐
      | 3. 导师/方向评估  |  <- 研究生阶段的真正核心
      |   实验室产出/去向  |     导师的研究方向=你未来3年的方向
      └───────┬────────┘
              ▼
      ┌───────▼────────┐
      | 4. 报录比/复试线  |  <- 数据驱动，勿凭感觉
      |   大小年规律      |     佐证层: 各校报录比数据
      └───────┬────────┘
              ▼
      ┌───────▼────────┐
      | 5. 调剂策略储备   |  <- 一定有备选
      |   B区院校兜底     |     哪些院校常年接收调剂
      └───────┬────────┘
              ▼
         最终建议输出
```

#### Phase 2 实现要点

- 新增考研专用佐证表：各校报录比、复试线、学科评估等级、常接收调剂的院校清单
- 新增 postgraduate 场景标签，路由时从 volunteer 中分离
- 考研 System Prompt 片段（替代高考五步链）
- 语料库需补充张雪峰考研相关内容的专项采集

### F.2 专业横向对比

#### 触发条件

当用户问题包含以下模式时，走对比流程：
- A 和 B 哪个好
- A vs B
- A 和 B 的区别
- 选 A 还是选 B

#### 对比维度

| 维度 | 数据来源 | 示例 |
|------|---------|------|
| 专业壁垒 | majors.barrier_level | 计算机(高) vs 市场营销(低) |
| 就业面宽度 | 佐证层就业趋势 + 语料观点 | 计算机: 全行业 / 临床: 医疗行业 |
| 薪酬区间 | employment_trends.avg_salary | 应届 8-15k vs 6-10k |
| 考研必要性 | 语料层观点 | 计算机: 看方向 / 临床: 必须读研 |
| AI 替代风险 | 语料层观点 + 趋势数据 | 翻译(高) vs 心理咨询(低) |
| 典型院校梯度 | admission_scores | 冲刺/稳妥/保底各三所 |

#### 输出格式

以表格对比为核心，每维度附一条数据来源标注。对比结束后给出：如果张雪峰来看，他会怎么说（思维层推理）。

#### 实现方式

在路由层新增 comparison 标签，检测到对比意图后：
1. 分别检索两个专业的语料和佐证数据
2. 按对比维度表中的字段做结构化提取
3. 用 LLM 生成对比表格 + 最终建议


### F.3 数据采集爬虫详细设计

#### 采集架构

```
采集调度器 (Scheduler)
    |
    +-- 公众号采集器 (WeChatCrawler)
    |   源: mp.weixin.qq.com
    |   方式: 搜狗微信搜索 + 账号主页
    |   频率: 每周
    |
    +-- B站视频采集器 (BilibiliCrawler)
    |   源: bilibili.com
    |   方式: API + yt-dlp 下载
    |   频率: 每周
    |
    +-- 知乎采集器 (ZhihuCrawler)
    |   源: zhihu.com
    |   方式: 话题搜索 + 高赞回答
    |   频率: 每两周
    |
    +-- 就业数据采集器 (JobDataCollector)
    |   源: 36氪/BOSS直聘公开报告
    |   方式: RSS + 页面解析
    |   频率: 月度
    |
    +-- 政策采集器 (PolicyCollector)
        源: 教育部/各省考试院官网
        方式: 页面解析 + 文件下载
        频率: 年度/按需
```

#### 反爬与合规策略

```python
class EthicalCrawler:
    """所有爬虫遵循的基类"""
    REQUEST_INTERVAL = 3.0        # 请求间隔 >= 3秒
    MAX_REQUESTS_PER_HOUR = 100   # 每小时上限
    RANDOM_JITTER = (0.5, 2.0)    # 随机抖动，避免机器行为特征
    
    USER_AGENT = "ZhangXuefengBot/1.0 (Educational Research)"
    RESPECT_ROBOTS_TXT = True
    SKIP_PAYWALL = True           # 不爬付费内容
    
    MAX_RETRIES = 3
    RETRY_BACKOFF = [60, 300, 900]  # 1分钟, 5分钟, 15分钟

    def should_crawl(self, url):
        if self.SKIP_PAYWALL and self._is_paywall(url):
            return False
        if not self._check_robots(url):
            return False
        return True
```

#### 采集 Pipeline

```
原始采集
    |
    v
格式标准化 (统一为 {source, url, title, content, date, author})
    |
    v
文本清洗 (去除HTML标签、广告、无关推荐)
    |
    v
质量过滤
    +-- 字数 < 100     -> 丢弃
    +-- 重复内容        -> 去重 (SimHash)
    +-- 广告/软文       -> LLM 快速分类 -> 丢弃
    |
    v
入库 (SQLite raw_data 表, 状态: pending_review)
    |
    v
人工抽查 (随机抽10%检查质量) -> approved -> 进入索引管线
```

#### 视频转录 Pipeline

```
视频下载 (yt-dlp)
    |
    v
音频提取 (ffmpeg: 16kHz mono WAV)
    |
    v
Whisper 转录 (medium 模型，中文识别)
    |
    v
说话人分离 (可选: pyannote-audio)
    |   标注: 张雪峰 / 家长 / 其他
    v
QA 对提取
    +-- 正则匹配: "问:" / "家长说:" / "同学说:"
    +-- LLM 辅助: 长段落中识别问答边界
    +-- 输出: [{question, answer, speaker, timestamp}]
    |
    v
入库 (与文本采集走同一清洗管线)
```

#### 错误处理

采集失败不阻塞整体流程，单条失败记录到 error_log。按错误类型分类处理：
- 网络错误: 自动重试3次，指数退避
- 限流: 等待后换IP重试
- 解析错误: 记录并跳过，通知人工检查
- 版权/付费墙: 记录并跳过，不重试

#### 监控

```
# SQLite 采集监控表
CREATE TABLE crawl_monitor (
    id          INTEGER PRIMARY KEY,
    source      TEXT,         -- 采集源
    run_at      TEXT,         -- 运行时间
    items_total INTEGER,      -- 采集到多少条
    items_new   INTEGER,      -- 新增多少条
    items_failed INTEGER,     -- 失败多少条
    duration_s  REAL,         -- 耗时
    error_log   TEXT          -- 错误详情 (JSON)
);
```

### F.4 前端交互详细设计

#### 全局状态栏

页面顶部常驻状态栏，每个服务一个圆点指示器：

```
[ZhangXuefeng Agent v1.0]    ChromaDB 🟢  SQLite 🟢  LLM 🟢  Reranker 🟢  Embed 🟢
```

- 绿色：正常
- 橙色：降级中（悬停显示降级原因）
- 红色：不可用（悬停显示修复建议）
- 点击任一指示器弹出详情面板：最后检查时间、最近错误、建议操作

#### 智能问答 Tab — 加载态

```
用户发送消息后:

[streaming]
用户: 河南理科580分计算机推荐什么学校
Agent: 你是河南理科，580分我先帮你看看位次... █      <- 逐字流式输出
       ^---- cursor blinking
       
[如果检索慢，> 2s 显示提示]
Agent: 正在检索张老师的相关观点和最新录取数据... （2-3秒）
       然后开始流式输出
```

#### 智能问答 Tab — 错误态

```
[LLM 超时]
Agent: 回答生成超时，正在重试... [1/3]

[LLM 全部失败（最终兜底）]
Agent: 抱歉，我暂时无法生成完整回答。以下是我找到的最相关内容：
       
       [折叠面板: 检索到的原始语料 Top-3]
       1. 2024.03 B站直播-张雪峰谈计算机专业选择
       2. 2025.01 公众号-关于土木工程行业变化的看法
       3. ...
       
       请稍后重试，或切换到 /health 查看系统状态。
```

#### 智能问答 Tab — 空结果态

```
[检索未命中任何相关内容]
Agent: 这个问题我目前掌握的信息不够。根据我的经验逻辑推断:
       [基于思维层的有限推理]
       
       ⚠ 注意：以上是我的推理，不代表张老师的具体观点。
       建议你查阅省教育考试院官网获取准确信息。
```

#### 志愿评估 Tab — 表单验证

```
省份: [下拉选择]  必填
科类: [单选: 物理类/历史类/综合改革]  必填
选科组合: [多选: 物理/化学/生物/历史/地理/政治]  新高考省份必填
分数: [数字输入]  必填，200-750范围校验
位次: [数字输入]  可选（更推荐填位次）
意向专业: [多选 + 搜索]  可选
意向城市: [多选]  可选
意向院校层次: [多选: 985/211/双一流/公办本科/民办]  可选
倾向: [单选: 省内优先/出省也可/无所谓]

[提交按钮] -> 禁用防重复 -> 显示进度条: 
  检索数据中... [▓▓░░░░] 40%
  生成报告中... [▓▓▓▓░░] 80%

结果区域:
  +-- 分数定位分析
  +-- 推荐院校（冲刺/稳妥/保底 三级）
  +-- 专业匹配度
  +-- 就业前景
  +-- 风险提示
  +-- [导出按钮] [分享按钮]
```

#### 语录搜索 Tab

```
搜索框: [________] [搜索按钮]
筛选:
  内容类型: [全部 ▼] [直播切片] [公众号] [访谈] [书籍]
  时间范围: [全部 ▼] [近1年] [近2年] [自定义]
  话题标签: [计算机] [医学] [金融] [师范] ... (标签云)

结果列表 (每页10条):
┌─────────────────────────────────────────┐
│ [直播切片] 2024.03.15  B站              │
│ 计算机专业一定要看城市，你在小城市学计算  │
│ 机出来跟在大城市学的完全是两个概念...     │
│ [查看原文] [查看完整上下文]              │
└─────────────────────────────────────────┘
```

#### 知识库管理 Tab（后台）

- 上传素材：拖拽上传 .mp4/.txt/.pdf，自动进采集管线
- 索引状态：总chunk数 / 今日新增 / 待审核 / 索引健康度
- 佐证数据管理：分数线表格浏览/编辑、就业趋势手动更新
- 日志查看：最近50条 ERROR + WARNING，支持筛选组件

#### 移动端适配

Gradio 默认响应式，但需关注：
- 状态栏在窄屏折叠为图标
- 志愿评估表单在小屏堆叠
- 语录搜索结果卡片自适应宽度


---

## 附录 G：配置管理

### G.1 配置文件结构

```python
# config.py
import os
from dataclasses import dataclass

@dataclass
class Config:
    # LLM
    llm_primary_model: str = "claude-sonnet-4-6"
    llm_primary_api_key: str = ""  # from env ZXF_LLM_PRIMARY_API_KEY
    llm_fallback_model: str = "deepseek-chat"
    llm_fallback_api_key: str = ""  # from env ZXF_LLM_FALLBACK_API_KEY
    llm_timeout: int = 30
    
    # Embedding
    embedding_mode: str = "api"  # "api" | "local"
    embedding_api_key: str = ""  # from env ZXF_EMBEDDING_API_KEY
    embedding_model: str = "BAAI/bge-m3"
    
    # Reranker
    reranker_mode: str = "api"  # "api" | "local"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    
    # Storage
    chroma_persist_dir: str = "data/chroma_db"
    sqlite_path: str = "data/zhangxuefeng.db"
    
    # UI
    gradio_port: int = 7860
    gradio_share: bool = False
    
    # Limits
    max_concurrent_requests: int = 10
    rate_limit_per_user: int = 2  # per second
    
    # Logging
    log_dir: str = "logs"
    log_level: str = "INFO"
    log_retention_days: int = 30


def load_config() -> Config:
    config = Config()
    for field in Config.__dataclass_fields__:
        env_val = os.getenv(f"ZXF_{field.upper()}")
        if env_val is not None:
            setattr(config, field, env_val)
    return config
```

### G.2 启动检查清单

启动时自动检查:
1. SQLite 数据库文件是否存在且可读写
2. ChromaDB 数据目录是否存在
3. LLM API key 是否已配置
4. Embedding API key 是否已配置
5. logs/ 目录是否可写
6. 各服务健康检查

任一检查失败 -> 启动时打印错误 + 修复建议，拒绝启动。

### G.3 文档最终版本信息

```
D:/zhangxuefengagent/README.md
├── 16 个正文章节
├── 附录 A: 内容安全与合规层
├── 附录 B: P0 缺口补全 (新高考/多轮对话/RAG评估)
├── 附录 C: P1 缺口补全 (特殊招生/时间敏感性/增量索引/流式/引用)
├── 附录 D: P2 待办项 (13项)
├── 附录 E: 剩余 P0 缺口 (System Prompt/Few-shot/测试策略/Embedding)
├── 附录 F: 剩余 P1 缺口 (考研框架/专业对比/爬虫/前端交互)
└── 附录 G: 配置管理
```

> 文档版本: v2.0
> 更新日期: 2026-06-20
> 状态: 设计阶段完成，已覆盖全部识别缺口
> 下一阶段: 实施规划 (writing-plans)

---
