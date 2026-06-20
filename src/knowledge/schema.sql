-- ============================================================
-- 张雪峰知识蒸馏 Agent - SQLite Schema
-- ============================================================
-- 佐证层 (Evidence Layer): 结构化的高校、专业、就业数据
-- 语料层 (Corpus Layer):    FTS5 全文检索，存储直播/视频/文章原文
-- 运维层 (Ops Layer):      索引追踪 & 采集监控
-- ============================================================

-- ── 佐证层表结构 ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS universities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    province TEXT NOT NULL,
    city TEXT NOT NULL,
    tier TEXT,          -- 985/211/双一流/普通
    type TEXT,          -- 综合/理工/师范/医学
    is_public INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS admission_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id INTEGER REFERENCES universities(id),
    province TEXT NOT NULL,
    year INTEGER NOT NULL,
    category TEXT NOT NULL,     -- 物理类/历史类/综合改革
    selection_combo TEXT,       -- 选科组合 如"物化生"
    batch TEXT NOT NULL,
    min_score INTEGER,
    min_rank INTEGER,
    major TEXT,
    source TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_admission_lookup
    ON admission_scores(province, year, category, min_score);

CREATE TABLE IF NOT EXISTS majors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    name TEXT NOT NULL,
    category TEXT,
    sub_category TEXT,
    barrier_level TEXT,      -- 高/中/低
    description TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS major_selection_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    major_id INTEGER REFERENCES majors(id),
    province TEXT NOT NULL,
    year INTEGER NOT NULL,
    required_subjects TEXT,
    optional_subjects TEXT,
    selection_count INTEGER DEFAULT 1,
    source TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS employment_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    major TEXT NOT NULL,
    major_id INTEGER REFERENCES majors(id),
    industry TEXT,
    trend TEXT NOT NULL,       -- 上升/持平/下行
    confidence REAL DEFAULT 0.5,
    signal_count INTEGER DEFAULT 1,
    signals TEXT,              -- JSON
    avg_salary TEXT,
    demand_ratio TEXT,
    source TEXT,
    period TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS city_industries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    province TEXT NOT NULL,
    cluster TEXT NOT NULL,
    scale TEXT,
    major_companies TEXT,
    source TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS major_university (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    major_id INTEGER REFERENCES majors(id),
    university_id INTEGER REFERENCES universities(id),
    ranking_grade TEXT,
    is_key_major INTEGER DEFAULT 0,
    source TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- ── 语料层 FTS5 表 ──────────────────────────────────────────

CREATE VIRTUAL TABLE IF NOT EXISTS corpus_fts USING fts5(
    content,
    source,
    content_type,
    date,
    topic,
    stance,
    source_url,
    chunk_index
);

-- ── 索引追踪表 ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS indexing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    content_type TEXT NOT NULL,
    chunk_count INTEGER,
    chroma_ids TEXT,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_source_hash ON indexing_log(source_hash);

-- ── 采集监控表 ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS crawl_monitor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    run_at TEXT DEFAULT (datetime('now')),
    items_total INTEGER,
    items_new INTEGER,
    items_failed INTEGER,
    duration_s REAL,
    error_log TEXT
);
