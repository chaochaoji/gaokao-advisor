# 志愿评估 v1 — 结构化卡片展示

**日期**: 2026-06-24
**范围**: 前后端改造，LLM 输出结构化 JSON，前端组件化卡片 + 三档可视化 + 会话历史
**工期**: 1 天 MVP

## 数据模型

LLM 输出的 JSON schema，前端根据 `min_rank` 和 `user_rank` 自行计算 `probability`：

```json
{
  "summary": {
    "position": "你的位次约 12,000-13,000 名",
    "score": 600,
    "rank": 12500,
    "rank_range": [12000, 13000],
    "advice": "建议冲刺2-3所，稳妥填报3-4所，保底2-3所"
  },
  "schools": [
    {
      "name": "北京工业大学",
      "city": "北京",
      "type": "211",
      "tier": "稳妥",
      "majors": ["计算机科学与技术", "软件工程"],
      "min_score": 595,
      "min_rank": 11500,
      "reason": "计算机学科评估B+，北京市属211，实习资源丰富",
      "tags": ["B+"],
      "risk_note": "计算机专业竞争激烈，建议填在第一专业"
    }
  ],
  "major_analysis": {
    "summary": "计算机类专业近三年就业率稳定在92%以上...",
    "pros": ["需求量大", "薪资起点高"],
    "cons": ["35岁天花板", "部分细分方向需读研"],
    "grad_school_rate": "约40%选择继续深造"
  },
  "risks": [
    "2025年北京物理类竞争加剧，位次可能上浮5%",
    "部分院校数据为2024年，建议核实最新招生章程"
  ],
  "data_year": "2025",
  "data_sources": ["2025年北京市一分一段表", "2024年各院校录取数据"]
}
```

### probability 计算规则（前端）

```js
function calcProbability(userRank, schoolMinRank) {
  const ratio = userRank / schoolMinRank;
  if (ratio >= 1.05) return Math.min(0.95, 0.6 + (ratio - 1.05) * 2);
  if (ratio >= 0.95) return 0.5 + (ratio - 0.95) * 5;
  return Math.max(0.1, 0.3 - (0.95 - ratio) * 2);
}
// 映射到 tier:
//   ratio >= 1.05 → 保底 (高概率)
//   0.95 <= ratio < 1.05 → 稳妥
//   ratio < 0.95 → 冲刺 (低概率)
```

概率条颜色：绿色 ≥80% / 蓝色 50-80% / 橙色 <50%。

## 前端布局

```
┌──────────────────────────────────────────────────────┐
│  📍 位次定位                                         │
│  ┌──────────────────────────────────────────────┐    │
│  │ 你的分数 600分  →  位次约 12,000-13,000 名   │    │
│  │ 2025年 北京 物理类                            │    │
│  │ 建议冲刺2所 · 稳妥3所 · 保底2所               │    │
│  └──────────────────────────────────────────────┘    │
│                                                       │
│  🎯 院校推荐                        [冲刺] [稳妥] [保底] │
│  ┌──────────────────────────────────────────────┐    │
│  │  ┌── card ──┐  ┌── card ──┐                 │    │
│  │  │ 院校名    │  │ 院校名    │                 │    │
│  │  │ [tag] tier│  │ [tag] tier│                 │    │
│  │  │ 专业列表  │  │ 专业列表  │                 │    │
│  │  │ 最低分/位次│  │ 最低分/位次│                 │    │
│  │  │ ████░░ 72%│  │ ████░░ 45%│                 │    │
│  │  │ 推荐理由  │  │ 推荐理由  │                 │    │
│  │  └──────────┘  └──────────┘                 │    │
│  └──────────────────────────────────────────────┘    │
│                                                       │
│  📊 专业与就业分析                                    │
│  ⚠️ 风险提示                                         │
│  📎 数据来源                                         │
└──────────────────────────────────────────────────────┘
```

### 交互

- 顶部 tier 标签 `[冲刺] [稳妥] [保底] [全部]` 可筛选卡片
- 概率条颜色编码
- 历史会话点击直接渲染卡片视图

### 实现方式

纯 vanilla JS + 模板字符串，零外部依赖。延续现有 `renderVolunteerForm` 的 DOM 操作风格。

## 数据流与会话持久化

```
POST /api/tools/volunteer
  → LLM 生成 JSON
  → schema 校验 + fallback 解析
  → session_store.add_turn(sid, user_msg, {
        content_type: "volunteer_assessment",
        structured_data: {...},
        fallback_text: "原始Markdown"
    })
  → 返回 { session_id, structured_data, sources }
  → 前端渲染卡片

GET /api/conversations/{sid}/messages
  → content_type === "volunteer_assessment" → 渲染卡片
  → content_type 为空/"text" → 渲染 Markdown (向后兼容)
```

### 关键实现点

1. `session_store.add_turn` 的 response 参数从 `str` 扩展为 `str | dict`
2. 旧数据 `content_type` 为空 → 纯文本渲染，不迁移
3. LLM JSON 不合法时：regex fallback 提取院校列表 → 成功则渲染降级卡片，失败则回退纯文本

## 涉及文件

| 文件 | 改动 |
|------|------|
| `src/utils/prompt_templates.py` | 新增 `VOLUNTEER_JSON_PROMPT`，定义 JSON 输出格式 |
| `src/agent/volunteer.py` | `handle()` 在 form 模式下走 JSON prompt |
| `src/api/tools.py` | `/tools/volunteer` 调用 JSON 输出路径，schema 校验，存储结构化数据 |
| `src/knowledge/session_store.py` | `add_turn` 支持 dict 类型的 response |
| `static/js/app.js` | 新增 `renderVolunteerResult()` 组件渲染函数 |
| `static/js/chat.js` | `renderMessages()` 根据 `content_type` 分发渲染 |
| `static/js/sidebar.js` | `selectSession()` 恢复历史评估卡片视图 |
| `static/css/style.css` | 新增卡片、概率条、tier 标签样式 |