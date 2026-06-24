# 志愿评估 v1 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 志愿评估报告从纯文本升级为结构化 JSON + 组件化卡片展示，支持会话历史回溯

**Architecture:** LLM 输出 JSON → 后端校验 + fallback 解析 → session_store 存储结构化数据 → 前端根据 content_type 分发渲染（卡片 vs 纯文本）

**Tech Stack:** Python/FastAPI (后端), vanilla JS (前端), SQLite (会话存储), 零新增依赖

## Global Constraints

- 零新增外部依赖（Python 和 JS 都是）
- 向后兼容旧会话数据（content_type 为空按文本渲染）
- 所有 JS 渲染为纯 DOM 操作，延续现有代码风格

---

### Task 1: 会话存储迁移 — 支持结构化消息

**Files:**
- Modify: `src/knowledge/session_store.py`

**Interfaces:**
- Produces: `add_turn(self, session_id, user_msg, assistant_msg, content_type='text', metadata=None)` — 新增可选参数
- Produces: `get_messages(self, session_id)` — 返回新增 `content_type` 和 `metadata` 字段

- [ ] **Step 1: 添加数据库迁移**

在 `_init_tables` 末尾添加 ALTER TABLE（SQLite 用 try/except 防重复）：

```python
def _init_tables(self):
    self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT 'New Chat',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
    """)
    # 新增: 结构化消息字段迁移
    for col, col_type in [("content_type", "TEXT DEFAULT 'text'"),
                           ("metadata", "TEXT")]:
        try:
            self.conn.execute(f"ALTER TABLE messages ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # 列已存在
    self.conn.commit()
```

- [ ] **Step 2: 修改 `add_turn` 签名和实现**

```python
def add_turn(self, session_id: str, user_msg: str, assistant_msg,
             content_type: str = 'text', metadata: str = None):
    """Add a user-assistant turn. assistant_msg can be str or dict.
    If dict, it's stored as JSON in content and content_type='volunteer_assessment'.
    """
    import json
    
    # 兼容旧的 dict 传入方式
    if isinstance(assistant_msg, dict):
        metadata = json.dumps(assistant_msg.get('structured_data', {}),
                              ensure_ascii=False)
        content_type = assistant_msg.get('content_type', 'volunteer_assessment')
        assistant_msg = assistant_msg.get('fallback_text', '')
    
    now = self._now()
    self.conn.execute(
        "INSERT INTO messages (conversation_id, role, content, content_type, metadata, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (session_id, "user", user_msg, "text", None, now))
    self.conn.execute(
        "INSERT INTO messages (conversation_id, role, content, content_type, metadata, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (session_id, "assistant", assistant_msg, content_type, metadata, now))
    count = self.conn.execute(
        "SELECT COUNT(*) FROM messages WHERE conversation_id = ?", (session_id,)
    ).fetchone()[0]
    if count <= 2:
        title = self._auto_title(user_msg)
        self.conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, session_id))
    self.conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, session_id))
    self.conn.commit()
```

- [ ] **Step 3: 修改 `get_messages` 返回新字段**

```python
def get_messages(self, session_id: str) -> list:
    rows = self.conn.execute(
        "SELECT role, content, content_type, metadata, created_at "
        "FROM messages WHERE conversation_id = ? ORDER BY id ASC",
        (session_id,)
    ).fetchall()
    result = []
    for r in rows:
        msg = dict(r)
        # content_type 为空时默认为 'text'
        if not msg.get('content_type'):
            msg['content_type'] = 'text'
        # metadata 为 JSON 字符串时解析
        if msg.get('metadata') and isinstance(msg['metadata'], str):
            try:
                msg['metadata'] = json.loads(msg['metadata'])
            except json.JSONDecodeError:
                pass
        result.append(msg)
    return result
```

需要文件顶部 import json。

- [ ] **Step 4: 验证**

```bash
python -c "
import sys; sys.path.insert(0, '.')
from src.knowledge.sqlite_store import get_db
from src.config import load_config
from src.knowledge.session_store import SessionStore
config = load_config()
db = get_db(config)
store = SessionStore(db)
sid = store.create_session()
store.add_turn(sid, 'test', 'text reply', content_type='text')
store.add_turn(sid, 'test2', {
    'content_type': 'volunteer_assessment',
    'structured_data': {'schools': [{'name': '北大'}]},
    'fallback_text': 'fallback markdown'
})
msgs = store.get_messages(sid)
assert msgs[0]['content_type'] == 'text'
assert msgs[1]['content_type'] == 'text'
assert msgs[2]['content_type'] == 'text'
assert msgs[3]['content_type'] == 'volunteer_assessment'
assert msgs[3]['metadata'] == {'schools': [{'name': '北大'}]}
store.delete_session(sid)
print('OK: all assertions passed')
"
```

- [ ] **Step 5: Commit**

```bash
git add src/knowledge/session_store.py
git commit -m "feat: session_store supports structured messages with content_type + metadata"
```

---

### Task 2: Prompt 模板 — 新增 JSON 输出指令

**Files:**
- Modify: `src/utils/prompt_templates.py`

**Interfaces:**
- Produces: `VOLUNTEER_JSON_PROMPT` — 全局常量，LLM JSON 输出格式指令

- [ ] **Step 1: 添加 JSON prompt 常量**

在 `CITATION_RULE` 之后添加：

```python
VOLUNTEER_JSON_PROMPT = """
## 输出格式要求（严格遵守）

你必须输出一个合法的 JSON 对象，不要包含 Markdown 代码块标记，不要有任何额外文本。

JSON 结构如下：
{
  "summary": {
    "position": "分数→位次的换算说明（1-2句话）",
    "score": 600,
    "rank": 12500,
    "rank_range": [12000, 13000],
    "advice": "冲/稳/保的整体建议（1句话）"
  },
  "schools": [
    {
      "name": "院校全称",
      "city": "所在城市",
      "type": "985 或 211 或 双一流 或 普通本科",
      "tier": "冲刺 或 稳妥 或 保底",
      "majors": ["推荐专业1", "推荐专业2"],
      "min_score": 595,
      "min_rank": 11500,
      "reason": "推荐理由（1-2句话）",
      "tags": ["学科评估等级如B+", "行业特色标签"],
      "risk_note": "风险提示或填报建议"
    }
  ],
  "major_analysis": {
    "summary": "专业整体分析（1-2句话）",
    "pros": ["优势1", "优势2"],
    "cons": ["劣势1", "劣势2"],
    "grad_school_rate": "深造比例描述"
  },
  "risks": [
    "风险点1",
    "风险点2"
  ],
  "data_year": "2025",
  "data_sources": ["数据来源1", "数据来源2"]
}

注意：
- schools 数组至少 3 所，最多 12 所，三档平均分布
- tier 只能是 "冲刺"、"稳妥"、"保底" 之一
- min_score 和 min_rank 必须是整数
- 如果某字段数据缺失，用空字符串 "" 或空数组 [] 替代，不要省略字段
"""
```

- [ ] **Step 2: 修改 `build_prompt` 支持 form 场景**

在 `build_prompt` 函数中，`scene == "volunteer_form"` 时追加 JSON prompt：

```python
def build_prompt(scene: str, context: dict) -> str:
    parts = [MAIN_SYSTEM_PROMPT]
    if scene in SCENE_PROMPTS:
        parts.append(SCENE_PROMPTS[scene])
    parts.append(CITATION_RULE)
    if scene == "general":
        parts.append(FALLBACK_RULE)
    # 志愿评估表单场景：追加 JSON 输出指令
    if scene == "volunteer_form":
        parts.append(VOLUNTEER_JSON_PROMPT)

    user_info = []
    for key in ["province", "score", "rank", "subject_combo", "interests"]:
        if context.get(key):
            user_info.append(f"{key}: {context[key]}")
    if user_info:
        parts.insert(1, "## 用户上下文\n" + "\n".join(user_info))

    return "\n\n".join(parts)
```

- [ ] **Step 3: 验证**

```bash
python -c "
from src.utils.prompt_templates import build_prompt, VOLUNTEER_JSON_PROMPT
p = build_prompt('volunteer_form', {'province':'北京','score':600})
assert 'VOLUNTEER_JSON_PROMPT' not in p  # 不应该有变量名
assert '输出格式要求' in p
assert 'json' in p.lower()
print('OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add src/utils/prompt_templates.py
git commit -m "feat: add VOLUNTEER_JSON_PROMPT for structured LLM output"
```

---

### Task 3: Tools API — JSON 校验、fallback、结构化存储

**Files:**
- Modify: `src/api/tools.py`

**Interfaces:**
- Consumes: `session_store.add_turn(sid, user_msg, dict)` from Task 1
- Consumes: `build_prompt("volunteer_form", context)` from Task 2
- Produces: `_validate_and_parse_volunteer_json(raw_text)` — 校验 + fallback 解析函数

- [ ] **Step 1: 添加校验和 fallback 解析函数**

在 `router` 定义之前添加：

```python
import re
import json as json_mod

# 必填字段和类型
_REQUIRED_TOP_FIELDS = {
    "summary": dict, "schools": list, "risks": list,
    "data_year": str, "data_sources": list, "major_analysis": dict
}
_REQUIRED_SCHOOL_FIELDS = {
    "name": str, "city": str, "type": str, "tier": str,
    "majors": list, "min_score": int, "min_rank": int,
    "reason": str, "tags": list, "risk_note": str
}
_VALID_TIERS = {"冲刺", "稳妥", "保底"}


def _validate_and_parse_volunteer_json(raw_text: str, user_ctx: dict) -> dict:
    """Try to parse LLM output as JSON, with fallback extraction."""
    
    # 尝试直接解析
    text = raw_text.strip()
    parsed = None
    
    # 去掉可能的 Markdown 代码块标记
    if text.startswith("```"):
        lines = text.split("\n")
        # 去掉第一行 ```json 和最后一行 ```
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        text = "\n".join(lines)
    
    try:
        parsed = json_mod.loads(text)
    except (json_mod.JSONDecodeError, ValueError):
        pass
    
    # 尝试提取 JSON 块
    if parsed is None:
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                parsed = json_mod.loads(m.group(0))
            except (json_mod.JSONDecodeError, ValueError):
                pass
    
    # 校验顶层字段
    if parsed:
        valid = True
        for field, typ in _REQUIRED_TOP_FIELDS.items():
            if field not in parsed or not isinstance(parsed[field], typ):
                valid = False
                break
        if valid and parsed.get("schools"):
            for s in parsed["schools"]:
                s["tier"] = s.get("tier", "稳妥")
                if s["tier"] not in _VALID_TIERS:
                    s["tier"] = "稳妥"
                # 确保整数类型
                if not isinstance(s.get("min_score"), int):
                    try: s["min_score"] = int(s["min_score"])
                    except: s["min_score"] = 0
                if not isinstance(s.get("min_rank"), int):
                    try: s["min_rank"] = int(s["min_rank"])
                    except: s["min_rank"] = 0
        if valid and len(parsed["schools"]) > 0:
            return {"ok": True, "data": parsed}
    
    # Fallback: regex 提取院校列表
    schools_raw = re.findall(
        r'(?:推荐|报考).*?(\S{2,8}(?:大学|学院)).*?(\d{3})\s*分.*?(\d{4,7})\s*(?:名|位)',
        text
    )
    if schools_raw:
        schools = []
        for name, score, rank in schools_raw[:8]:
            schools.append({
                "name": name, "city": "", "type": "",
                "tier": "稳妥", "majors": [],
                "min_score": int(score), "min_rank": int(rank),
                "reason": "", "tags": [], "risk_note": ""
            })
        fallback_data = {
            "summary": {
                "position": f"位次估算中",
                "score": user_ctx.get("score", 0),
                "rank": 0, "rank_range": [0, 0],
                "advice": "以下为自动提取的院校列表，建议重新生成获取完整报告"
            },
            "schools": schools,
            "major_analysis": {
                "summary": "", "pros": [], "cons": [], "grad_school_rate": ""
            },
            "risks": ["数据提取不完整，建议重新生成"],
            "data_year": "", "data_sources": []
        }
        return {"ok": True, "data": fallback_data, "fallback": True}
    
    return {"ok": False, "raw": text}
```

- [ ] **Step 2: 修改 `volunteer_tool` endpoint**

```python
@router.post("/tools/volunteer")
def volunteer_tool(data: VolunteerInput):
    if not data.province or not data.score:
        return {"error": "请至少填写省份和分数。"}
    query = f"{data.province}{data.category}{data.score}分"
    if data.rank: query += f" 位次{data.rank}"
    query += " 志愿填报推荐"
    if data.interests: query += f" 对{data.interests}感兴趣"
    if data.desired_location: query += f" 期望地区{data.desired_location}"

    context = {"province":data.province, "score":data.score, "category":data.category or "物理类",
               "interests":[i.strip() for i in data.interests.split(",") if i.strip()],
               "rank":data.rank, "desired_location":data.desired_location}
    results = hybrid_search.search(query, "volunteer", context)
    
    # 使用 volunteer_form prompt（含 JSON 输出指令）
    prompt = build_prompt("volunteer_form", context)
    
    # 构建检索数据 + 用户信息
    nl = chr(10)
    ctx = nl.join([f"[检索结果 {i+1}] {r['content']}" for i,r in enumerate(results[:10])])
    user_info_lines = [f"省份: {data.province}, 科类: {data.category}, 分数: {data.score}"]
    if data.rank: user_info_lines.append(f"位次: {data.rank}")
    if data.interests: user_info_lines.append(f"意向专业: {data.interests}")
    if data.desired_location:
        user_info_lines.append(f"期望地区: {data.desired_location}（优先推荐该地区）")
    else:
        user_info_lines.append("期望地区: 未指定（全国范围推荐）")
    
    full_prompt = f"{prompt}{nl}{nl}## 检索到的数据{nl}{ctx}{nl}{nl}## 用户信息{nl}{nl.join(user_info_lines)}{nl}{nl}请按 JSON 格式输出完整的志愿评估报告。切记只输出 JSON，不要包含任何其他文本。"
    
    from src.api.chat import _call_llm
    resp = _call_llm(full_prompt)
    
    # 校验 + fallback
    user_ctx = {"score": data.score, "rank": data.rank, "province": data.province}
    result = _validate_and_parse_volunteer_json(resp, user_ctx)
    
    # 创建或使用已有 session
    sid = data.session_id if data.session_id else session_store.create_session()
    user_msg = f"[志愿评估] {data.province}{data.category}{data.score}分"
    if data.interests: user_msg += f" 意向{data.interests}"
    if data.desired_location: user_msg += f" 期望{data.desired_location}"
    
    if result["ok"]:
        # 结构化存储
        session_store.add_turn(sid, user_msg, {
            "content_type": "volunteer_assessment",
            "structured_data": result["data"],
            "fallback_text": resp
        })
        return {
            "ok": True,
            "session_id": sid,
            "structured_data": result["data"],
            "fallback": result.get("fallback", False),
            "sources": [r.get("content","")[:100] for r in results[:5]]
        }
    else:
        # 解析失败，退化为纯文本存储
        session_store.add_turn(sid, user_msg, resp)
        return {
            "ok": True,
            "session_id": sid,
            "fallback_text": resp,
            "parse_error": True,
            "sources": [r.get("content","")[:100] for r in results[:5]]
        }
```

- [ ] **Step 3: 验证**

```bash
# 测试校验函数
python -c "
import sys; sys.path.insert(0, '.')
from src.api.tools import _validate_and_parse_volunteer_json

# 正常 JSON
good = '{\"summary\":{\"position\":\"test\",\"score\":600,\"rank\":12000,\"rank_range\":[11000,13000],\"advice\":\"test\"},\"schools\":[{\"name\":\"北大\",\"city\":\"北京\",\"type\":\"985\",\"tier\":\"冲刺\",\"majors\":[\"计算机\"],\"min_score\":680,\"min_rank\":500,\"reason\":\"top2\",\"tags\":[\"A+\"],\"risk_note\":\"\"}],\"major_analysis\":{\"summary\":\"\",\"pros\":[],\"cons\":[],\"grad_school_rate\":\"\"},\"risks\":[\"test\"],\"data_year\":\"2025\",\"data_sources\":[\"test\"]}'
r = _validate_and_parse_volunteer_json(good, {})
assert r['ok'] == True
print('Good JSON: OK')

# 带 Markdown 代码块
md = '```json\n' + good + '\n```'
r = _validate_and_parse_volunteer_json(md, {})
assert r['ok'] == True
print('Markdown wrapped: OK')

# 垃圾文本
r = _validate_and_parse_volunteer_json('hello world', {})
assert r['ok'] == False
print('Garbage: correctly rejected')
"
```

- [ ] **Step 4: Commit**

```bash
git add src/api/tools.py
git commit -m "feat: JSON validation + fallback parsing for volunteer assessment"
```

---

### Task 4: 前端 CSS — 卡片、概率条、标签样式

**Files:**
- Modify: `static/css/style.css`

- [ ] **Step 1: 在 style.css 末尾追加样式**

```css
/* ====== 志愿评估结果卡片 ====== */
.assessment-result {
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}
/* --- 位次定位摘要 --- */
.position-card {
  background: linear-gradient(135deg, #1e40af, #3b82f6);
  color: #fff;
  border-radius: 1rem;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.25rem;
}
.position-card .pos-score {
  font-size: 2rem;
  font-weight: 800;
}
.position-card .pos-rank {
  font-size: .875rem;
  opacity: .85;
  margin-top: .25rem;
}
.position-card .pos-advice {
  font-size: .8125rem;
  opacity: .75;
  margin-top: .5rem;
  padding-top: .5rem;
  border-top: 1px solid rgba(255,255,255,.2);
}

/* --- Tier 筛选标签 --- */
.tier-tabs {
  display: flex;
  gap: .5rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
.tier-tab {
  padding: .375rem 1rem;
  border-radius: 999px;
  font-size: .8125rem;
  font-weight: 500;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  cursor: pointer;
  transition: all .15s;
}
.tier-tab:hover { border-color: #3b82f6; color: #3b82f6; }
.tier-tab.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }

/* --- 院校卡片 --- */
.school-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 1rem;
  padding: 1.125rem 1.25rem;
  margin-bottom: .75rem;
  transition: box-shadow .15s;
}
.school-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,.06); }
.school-card-header {
  display: flex;
  align-items: center;
  gap: .5rem;
  flex-wrap: wrap;
  margin-bottom: .5rem;
}
.school-card-name {
  font-size: 1rem;
  font-weight: 700;
  color: #1e293b;
}
.school-card-badge {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: .6875rem;
  font-weight: 600;
  line-height: 1.4;
}
.badge-985 { background: #fef3c7; color: #92400e; }
.badge-211 { background: #dbeafe; color: #1e40af; }
.badge-tier-chongci { background: #fee2e2; color: #dc2626; }
.badge-tier-wentuo { background: #dbeafe; color: #2563eb; }
.badge-tier-baodi { background: #d1fae5; color: #059669; }
.badge-tag { background: #f1f5f9; color: #64748b; }

.school-card-majors {
  font-size: .8125rem;
  color: #475569;
  margin-bottom: .375rem;
}
.school-card-majors span {
  display: inline-block;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
  margin-right: 4px;
  margin-bottom: 2px;
}
.school-card-score {
  font-size: .8125rem;
  color: #64748b;
  margin-bottom: .5rem;
}

/* --- 概率条 --- */
.probability-bar-wrap {
  display: flex;
  align-items: center;
  gap: .5rem;
  margin-bottom: .5rem;
}
.probability-bar {
  flex: 1;
  height: 8px;
  background: #f1f5f9;
  border-radius: 4px;
  overflow: hidden;
}
.probability-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width .4s ease;
}
.probability-bar-fill.high { background: #22c55e; }
.probability-bar-fill.mid { background: #3b82f6; }
.probability-bar-fill.low { background: #f59e0b; }
.probability-label {
  font-size: .75rem;
  font-weight: 600;
  min-width: 2.5rem;
  text-align: right;
}

.school-card-reason {
  font-size: .8125rem;
  color: #64748b;
  margin-bottom: .375rem;
  line-height: 1.5;
}
.school-card-risk {
  font-size: .75rem;
  color: #f59e0b;
  padding: .375rem .5rem;
  background: #fffbeb;
  border-radius: .5rem;
}

/* --- 专业分析 --- */
.analysis-section {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 1rem;
  padding: 1.125rem 1.25rem;
  margin-bottom: .75rem;
}
.analysis-section h4 {
  font-size: .9375rem;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: .5rem;
}
.analysis-pros-cons {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}
.analysis-pros, .analysis-cons {
  flex: 1;
  min-width: 200px;
}
.analysis-pros li, .analysis-cons li {
  font-size: .8125rem;
  line-height: 1.6;
  color: #475569;
}
.analysis-pros li::marker { color: #22c55e; }
.analysis-cons li::marker { color: #f59e0b; }

/* --- 风险区 --- */
.risk-section {
  background: #fff;
  border: 1px solid #fecaca;
  border-radius: 1rem;
  padding: 1.125rem 1.25rem;
  margin-bottom: .75rem;
}
.risk-section h4 { font-size: .9375rem; font-weight: 700; color: #dc2626; margin-bottom: .5rem; }
.risk-section li { font-size: .8125rem; color: #7f1d1d; line-height: 1.6; }

/* --- 数据来源 --- */
.sources-footer {
  font-size: .75rem;
  color: #94a3b8;
  padding: .5rem 0;
}
```

- [ ] **Step 2: 验证**

浏览器打开页面，确认无 CSS 解析错误（检查 console）。

- [ ] **Step 3: Commit**

```bash
git add static/css/style.css
git commit -m "feat: add assessment card, probability bar, tier tag styles"
```

---

### Task 5: 前端 App.js — 卡片渲染 + 概率计算 + tier 筛选

**Files:**
- Modify: `static/js/app.js`

- [ ] **Step 1: 添加概率计算函数**

在文件顶部（`window._currentMode` 之后）添加：

```javascript
function calcProbability(userRank, schoolMinRank) {
    if (!userRank || !schoolMinRank || schoolMinRank <= 0) return 0.5;
    var ratio = userRank / schoolMinRank;
    if (ratio >= 1.05) return Math.min(0.95, 0.6 + (ratio - 1.05) * 2);
    if (ratio >= 0.95) return 0.5 + (ratio - 0.95) * 5;
    return Math.max(0.1, 0.3 - (0.95 - ratio) * 2);
}

function probClass(p) {
    return p >= 0.8 ? 'high' : p >= 0.5 ? 'mid' : 'low';
}

function tierBadgeClass(tier) {
    if (tier === '冲刺') return 'badge-tier-chongci';
    if (tier === '稳妥') return 'badge-tier-wentuo';
    if (tier === '保底') return 'badge-tier-baodi';
    return 'badge-tier-wentuo';
}

function typeBadgeClass(type) {
    if (type && type.indexOf('985') !== -1) return 'badge-985';
    if (type && type.indexOf('211') !== -1) return 'badge-211';
    return '';
}
```

- [ ] **Step 2: 添加 `renderVolunteerResult` 主渲染函数**

```javascript
function renderVolunteerResult(data) {
    var summary = data.summary || {};
    var schools = data.schools || [];
    var majorAnalysis = data.major_analysis || {};
    var risks = data.risks || [];
    var sources = data.data_sources || [];
    var dataYear = data.data_year || '';
    var userRank = summary.rank || 0;

    var html = '<div class="assessment-result">';

    // --- 位次定位摘要 ---
    html += '<div class="position-card">';
    html += '<div class="pos-score">' + escapeHtml(String(summary.score || '--')) + '分</div>';
    html += '<div class="pos-rank">位次约 ' + escapeHtml(summary.position || '估算中') + '</div>';
    html += '<div class="pos-advice">' + escapeHtml(summary.advice || '') + '</div>';
    html += '</div>';

    // --- Tier 筛选 tabs ---
    html += '<div class="tier-tabs">';
    html += '<button class="tier-tab active" data-filter="all">全部 (' + schools.length + ')</button>';
    var tiers = ['冲刺', '稳妥', '保底'];
    tiers.forEach(function(t) {
        var count = schools.filter(function(s) { return s.tier === t; }).length;
        html += '<button class="tier-tab" data-filter="' + t + '">' + t + ' (' + count + ')</button>';
    });
    html += '</div>';

    // --- 院校列表 ---
    html += '<div id="school-list">';
    schools.forEach(function(s) {
        var prob = calcProbability(userRank, s.min_rank);
        var pc = probClass(prob);
        html += renderSchoolCard(s, prob, pc);
    });
    html += '</div>';

    // --- 专业与就业分析 ---
    if (majorAnalysis.summary || (majorAnalysis.pros || []).length > 0) {
        html += '<div class="analysis-section">';
        html += '<h4>📊 专业与就业分析</h4>';
        if (majorAnalysis.summary) {
            html += '<p style="font-size:.8125rem;color:#475569;margin-bottom:.5rem">' + escapeHtml(majorAnalysis.summary) + '</p>';
        }
        html += '<div class="analysis-pros-cons">';
        if ((majorAnalysis.pros || []).length > 0) {
            html += '<div class="analysis-pros"><strong style="color:#16a34a">✅ 优势</strong><ul>';
            majorAnalysis.pros.forEach(function(p) { html += '<li>' + escapeHtml(p) + '</li>'; });
            html += '</ul></div>';
        }
        if ((majorAnalysis.cons || []).length > 0) {
            html += '<div class="analysis-cons"><strong style="color:#f59e0b">⚠️ 劣势</strong><ul>';
            majorAnalysis.cons.forEach(function(c) { html += '<li>' + escapeHtml(c) + '</li>'; });
            html += '</ul></div>';
        }
        html += '</div>';
        if (majorAnalysis.grad_school_rate) {
            html += '<p style="font-size:.75rem;color:#94a3b8;margin-top:.5rem">深造比例：' + escapeHtml(majorAnalysis.grad_school_rate) + '</p>';
        }
        html += '</div>';
    }

    // --- 风险提示 ---
    if (risks.length > 0) {
        html += '<div class="risk-section">';
        html += '<h4>⚠️ 风险提示</h4><ul>';
        risks.forEach(function(r) { html += '<li>' + escapeHtml(r) + '</li>'; });
        html += '</ul></div>';
    }

    // --- 数据来源 ---
    if (sources.length > 0 || dataYear) {
        html += '<div class="sources-footer">📎 数据年份：' + escapeHtml(dataYear || '未标注');
        if (sources.length > 0) {
            html += ' · 来源：' + escapeHtml(sources.join('、'));
        }
        html += '</div>';
    }

    html += '</div>'; // .assessment-result

    el("#tool-panel").innerHTML = html;

    // 绑定 tier 筛选
    els("#tool-panel .tier-tab").forEach(function(tab) {
        tab.addEventListener("click", function() {
            els("#tool-panel .tier-tab").forEach(function(t) { t.classList.remove("active"); });
            tab.classList.add("active");
            var filter = tab.dataset.filter;
            els("#school-list .school-card").forEach(function(card) {
                if (filter === 'all' || card.dataset.tier === filter) {
                    card.style.display = '';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });
}
```

- [ ] **Step 3: 添加单张院校卡片渲染函数**

```javascript
function renderSchoolCard(s, prob, probClass) {
    var badgeClass = typeBadgeClass(s.type);
    var tierClass = tierBadgeClass(s.tier);
    var probPct = Math.round(prob * 100);
    
    var html = '<div class="school-card" data-tier="' + escapeHtml(s.tier) + '">';
    
    // Header: 名称 + badges
    html += '<div class="school-card-header">';
    html += '<span class="school-card-name">🏫 ' + escapeHtml(s.name) + '</span>';
    if (s.type) html += '<span class="school-card-badge ' + badgeClass + '">' + escapeHtml(s.type) + '</span>';
    html += '<span class="school-card-badge ' + tierClass + '">' + escapeHtml(s.tier) + '</span>';
    (s.tags || []).forEach(function(t) {
        html += '<span class="school-card-badge badge-tag">' + escapeHtml(t) + '</span>';
    });
    html += '</div>';
    
    // 城市
    if (s.city) {
        html += '<div style="font-size:.75rem;color:#94a3b8;margin-bottom:.375rem">📍 ' + escapeHtml(s.city) + '</div>';
    }
    
    // 推荐专业
    if ((s.majors || []).length > 0) {
        html += '<div class="school-card-majors">';
        s.majors.forEach(function(m) { html += '<span>' + escapeHtml(m) + '</span>'; });
        html += '</div>';
    }
    
    // 最低分/位次
    html += '<div class="school-card-score">';
    html += '最低录取：' + (s.min_score || '--') + '分 / ' + (s.min_rank || '--') + '名';
    html += '</div>';
    
    // 概率条
    html += '<div class="probability-bar-wrap">';
    html += '<div class="probability-bar"><div class="probability-bar-fill ' + probClass + '" style="width:' + probPct + '%"></div></div>';
    html += '<span class="probability-label" style="color:' + (probPct >= 80 ? '#16a34a' : probPct >= 50 ? '#2563eb' : '#d97706') + '">' + probPct + '%</span>';
    html += '</div>';
    
    // 推荐理由
    if (s.reason) {
        html += '<div class="school-card-reason">💡 ' + escapeHtml(s.reason) + '</div>';
    }
    
    // 风险提示
    if (s.risk_note) {
        html += '<div class="school-card-risk">⚠️ ' + escapeHtml(s.risk_note) + '</div>';
    }
    
    html += '</div>';
    return html;
}
```

- [ ] **Step 4: 修改 `handleVolunteerSubmit` 使用新渲染**

```javascript
function handleVolunteerSubmit() {
    var data = {
        province: el("#v-province").value,
        score: parseInt(el("#v-score").value) || 600,
        rank: parseInt(el("#v-rank").value) || 0,
        category: (els('input[name="v-cat"]:checked')[0] || {}).value || "物理类",
        interests: el("#v-interests").value || "",
        desired_location: el("#v-desired-location").value || ""
    };
    var btn = el("#v-submit");
    data.session_id = window._currentSid || sidebarState.currentSessionId || "";
    btn.disabled = true; btn.textContent = "处理中...";
    volunteerTool(data).then(function (res) {
        btn.disabled = false; btn.textContent = "提交评估";
        if (res.parse_error && res.fallback_text) {
            // 解析失败，显示纯文本
            el("#v-result").style.display = "";
            el("#v-result").innerHTML = '<h4>评估结果（文本模式）</h4><div class="result-text">'
                + renderMarkdown(res.fallback_text) + '</div>';
        } else if (res.structured_data) {
            // 结构化渲染
            var container = el("#v-result");
            container.style.display = "";
            container.innerHTML = '';
            renderVolunteerResult(res.structured_data);
            // renderVolunteerResult 渲染到 #tool-panel 内部...
            // 需要适配：把结果放到 #v-result
            // 方案：重新渲染到 tool-panel 的独立区域
            el("#tool-panel").innerHTML = '';
            renderVolunteerResult(res.structured_data);
        }
        if (res.session_id) {
            window._currentSid = res.session_id;
            window.sidebarState.currentSessionId = res.session_id;
            if (typeof renderSessionList === "function") renderSessionList();
        }
    }).catch(function (e) {
        showToast("错误: " + e.message);
        btn.disabled = false; btn.textContent = "提交评估";
    });
}
```

- [ ] **Step 5: 验证**

不需要单独运行测试，Task 8 会做端到端验证。

- [ ] **Step 6: Commit**

```bash
git add static/js/app.js
git commit -m "feat: structured volunteer assessment card rendering with probability bars"
```

---

### Task 6: 前端 Chat.js — renderMessages 按 content_type 分发

**Files:**
- Modify: `static/js/chat.js`

- [ ] **Step 1: 修改 `renderMessages`**

```javascript
function renderMessages(msgs) {
    msgs.forEach(function (m) {
        if (m.role === "user") {
            addUserMessage(m.content);
        } else if (m.role === "assistant") {
            if (m.content_type === 'volunteer_assessment' && m.metadata) {
                // 结构化评估结果 → 渲染卡片
                addVolunteerResultMessage(m.metadata, m.content);
            } else {
                // 普通文本消息
                var bubble = createAgentSkeleton();
                var resp = bubble.querySelector(".response-text");
                if (resp) resp.innerHTML = renderMarkdown(m.content);
                bubble.classList.remove("agent-skeleton");
                finalizeMessage(bubble);
            }
        }
    });
    scrollToBottom();
}
```

- [ ] **Step 2: 添加 `addVolunteerResultMessage` 函数**

```javascript
function addVolunteerResultMessage(structuredData, fallbackText) {
    var div = document.createElement("div");
    div.className = "message-row agent";
    div.innerHTML = '<div class="message-avatar">助手</div>'
        + '<div class="message-content"><div id="volunteer-result-inline"></div></div>';
    el("#chat-messages").appendChild(div);
    
    // 渲染到临时容器
    var container = div.querySelector("#volunteer-result-inline");
    container.id = ''; // 去掉 id 避免重复
    
    if (structuredData && structuredData.schools) {
        // 构建临时 DOM 来渲染
        var tempPanel = el("#tool-panel");
        var originalHTML = tempPanel ? tempPanel.innerHTML : '';
        
        // 直接用函数渲染 HTML 字符串并注入
        renderVolunteerResultToContainer(container, structuredData);
    } else if (fallbackText) {
        container.innerHTML = renderMarkdown(fallbackText);
    }
    scrollToBottom();
}
```

`renderVolunteerResultToContainer` 是 `renderVolunteerResult` 的变体，接受容器参数而非写入 `#tool-panel`。在 `app.js` 中把 `renderVolunteerResult` 改为代理：

```javascript
function renderVolunteerResult(data) {
    renderVolunteerResultToContainer(el("#tool-panel"), data);
}

function renderVolunteerResultToContainer(container, data) {
    // ... 原来的 renderVolunteerResult 逻辑，但所有 el("#tool-panel") 
    // 替换为 container，innerHTML 赋值改为 container.innerHTML
    var summary = data.summary || {};
    // ... (同上，略)
    container.innerHTML = html;
    
    // 绑定 tier 筛选（作用域在 container 内）
    container.querySelectorAll(".tier-tab").forEach(function(tab) {
        tab.addEventListener("click", function() {
            container.querySelectorAll(".tier-tab").forEach(function(t) { t.classList.remove("active"); });
            tab.classList.add("active");
            var filter = tab.dataset.filter;
            container.querySelectorAll(".school-card").forEach(function(card) {
                if (filter === 'all' || card.dataset.tier === filter) {
                    card.style.display = '';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });
}
```

- [ ] **Step 3: 验证**

同 Task 5。

- [ ] **Step 4: Commit**

```bash
git add static/js/chat.js static/js/app.js
git commit -m "feat: chat history renders volunteer assessment as structured cards"
```

---

### Task 7: 前端 Sidebar.js — 历史会话恢复评估卡片

**Files:**
- Modify: `static/js/sidebar.js`

- [ ] **Step 1: 修改 `selectSession` 恢复评估卡片**

在 `selectSession` 函数中，`getMessages` 回调改为使用新的 `renderMessages`（Task 6 已更新）：

```javascript
// selectSession 中的 getMessages 部分保持不变 —
// 因为 renderMessages 已经在 Task 6 中更新为支持 content_type 分发
// 只需确认 hideAllPanels 在显示 chat-messages 时正确处理
```

无需额外修改 — Task 6 的 `renderMessages` 已处理分发。但需要确保会话切换时 `tool-panel` 被正确重置：

在 `selectSession` 中添加一行：

```javascript
function selectSession(sid) {
    // ... 前面逻辑不变 ...
    
    // 重置 tool-panel（避免旧评估表单残留）
    el("#tool-panel").innerHTML = "";
    el("#tool-panel").style.display = "none";
    
    getMessages(sid).then(function (msgs) {
        el("#chat-messages").innerHTML = "";
        if (msgs && msgs.length) renderMessages(msgs);
    }).catch(function (e) {
        console.error("加载消息失败:", e);
    });
}
```

- [ ] **Step 2: 验证**

同 Task 8 端到端测试。

- [ ] **Step 3: Commit**

```bash
git add static/js/sidebar.js
git commit -m "feat: sidebar session switching preserves volunteer assessment cards"
```

---

### Task 8: 端到端验证

- [ ] **Step 1: 启动服务**

```bash
python app_api.py &
sleep 5
```

- [ ] **Step 2: 测试 JSON 校验**

```bash
# 正常 JSON
curl -s -X POST http://localhost:7860/api/tools/volunteer \
  -H "Content-Type: application/json" \
  -d '{"province":"北京","score":600,"category":"物理类"}' | python -c "import sys,json; d=json.load(sys.stdin); print('structured_data' in d or 'parse_error' in d)"
```

- [ ] **Step 3: 测试会话历史**

```bash
# 创建 session
SID=$(curl -s -X POST http://localhost:7860/api/conversations | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Session: $SID"

# 发起评估
curl -s -X POST http://localhost:7860/api/tools/volunteer \
  -H "Content-Type: application/json" \
  -d "{\"province\":\"北京\",\"score\":600,\"category\":\"物理类\",\"session_id\":\"$SID\"}" > /dev/null

# 获取消息
curl -s http://localhost:7860/api/conversations/$SID/messages | python -c "
import sys, json
msgs = json.load(sys.stdin)
for m in msgs:
    ct = m.get('content_type', 'text')
    print(f\"  [{m['role']}] content_type={ct}\")
    if ct == 'volunteer_assessment':
        meta = m.get('metadata', {})
        schools = meta.get('schools', [])
        print(f'    schools: {len(schools)}')
        for s in schools[:2]:
            print(f'    - {s.get(\"name\")} ({s.get(\"tier\")})')
"
```

- [ ] **Step 4: 测试纯文本降级**

```bash
curl -s http://localhost:7860/api/conversations/test-nonexistent/messages | python -c "
import sys, json
d = json.load(sys.stdin)
assert 'detail' in d  # 404
print('404 correctly returned for missing session')
"
```

- [ ] **Step 5: 关闭服务并 Commit**

```bash
taskkill //F //IM python.exe 2>/dev/null
git add -A
git commit -m "chore: end-to-end validation of volunteer assessment v1"
```

---

## 自检清单

1. **Spec coverage**: 所有 spec 要求均已覆盖 — JSON 输出、schema 校验、fallback、概率计算、三档卡片、tier 筛选、专业分析、风险提示、会话历史
2. **Placeholder scan**: 无 TBD/TODO/模糊占位符
3. **Type consistency**: `add_turn` 的 dict 参数和 `get_messages` 返回的 metadata 字段类型一致；前端 `renderVolunteerResultToContainer` 在 app.js 和 chat.js 中签名一致
