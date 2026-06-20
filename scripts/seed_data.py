# -*- coding: utf-8 -*-
"""Seed data script for the Zhang Xuefeng Knowledge Distillation Agent.

Populates the SQLite database and ChromaDB collection with initial data:
  - 4 universities
  - 6 majors
  - 4 employment trends
  - 12 corpus chunks (both FTS5 entries and ChromaDB embeddings)

Usage:
    python scripts/seed_data.py [--config PATH]
"""
from __future__ import annotations

import os
import sys
import json
import argparse
import sqlite3
import uuid

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_ROOT = os.path.join(_PROJECT_ROOT, 'src')
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

from src.config import Config, load_config
from src.knowledge.sqlite_store import get_db, init_db, fts5_search
from src.knowledge.chroma_store import get_chroma_collection, add_chunks, query_chunks


# =============================================================================
# Seed data definitions
# =============================================================================

UNIVERSITIES = [
    {
        "name": "北京大学",
        "province": "北京",
        "city": "北京",
        "tier": "985",
        "type": "综合",
        "is_public": 1,
    },
    {
        "name": "华中科技大学",
        "province": "湖北",
        "city": "武汉",
        "tier": "985",
        "type": "理工",
        "is_public": 1,
    },
    {
        "name": "郑州大学",
        "province": "河南",
        "city": "郑州",
        "tier": "211",
        "type": "综合",
        "is_public": 1,
    },
    {
        "name": "深圳大学",
        "province": "广东",
        "city": "深圳",
        "tier": "双一流",
        "type": "综合",
        "is_public": 1,
    },
]

MAJORS = [
    {
        "code": "080901",
        "name": "计算机科学与技术",
        "category": "工学",
        "sub_category": "计算机类",
        "barrier_level": "中",
        "description": "研究计算机软硬件系统设计与开发，涵盖算法、数据结构、操作系统、计算机网络等核心领域，就业面广但竞争激烈。",
    },
    {
        "code": "080902",
        "name": "软件工程",
        "category": "工学",
        "sub_category": "计算机类",
        "barrier_level": "中",
        "description": "系统化的软件开发方法与工程管理，侧重大型软件项目的需求分析、设计、测试与维护全生命周期。",
    },
    {
        "code": "100201",
        "name": "临床医学",
        "category": "医学",
        "sub_category": "临床医学类",
        "barrier_level": "高",
        "description": "培养具备基础医学和临床医学知识的高级医疗人才，学制长、门槛高，但职业壁垒强，社会地位和收入稳定。",
    },
    {
        "code": "080703",
        "name": "土木工程",
        "category": "工学",
        "sub_category": "土木类",
        "barrier_level": "低",
        "description": "涵盖建筑工程、道路桥梁、岩土工程等方向，近年受房地产和基建下行影响，行业景气度下降。",
    },
    {
        "code": "020301",
        "name": "金融学",
        "category": "经济学",
        "sub_category": "金融学类",
        "barrier_level": "高",
        "description": "研究金融市场运作规律、资产定价与风险管理，头部金融岗位竞争激烈，对院校背景和人脉要求高。",
    },
    {
        "code": "050201",
        "name": "英语",
        "category": "文学",
        "sub_category": "外国语言文学类",
        "barrier_level": "低",
        "description": "培养英语语言能力和跨文化交际能力，随着AI翻译技术进步，纯语言类岗位需求下降，需结合其他专业技能。",
    },
]

EMPLOYMENT_TRENDS = [
    {
        "major": "计算机科学与技术",
        "major_id": None,  # Will be filled after insertion
        "industry": "互联网/IT",
        "trend": "上升",
        "confidence": 0.85,
        "signal_count": 3,
        "signals": json.dumps([
            {"source": "工信部", "indicator": "数字经济占GDP比重突破45%"},
            {"source": "招聘平台", "indicator": "AI工程师岗位同比增长36%"},
            {"source": "高校就业报告", "indicator": "计算机类就业率保持95%以上"},
        ], ensure_ascii=False),
        "avg_salary": "15-25万/年（本科起薪）",
        "demand_ratio": "2.8:1（岗位:求职者）",
        "source": "综合多源",
        "period": "2024-2025",
    },
    {
        "major": "软件工程",
        "major_id": None,
        "industry": "软件/互联网",
        "trend": "上升",
        "confidence": 0.80,
        "signal_count": 2,
        "signals": json.dumps([
            {"source": "BOSS直聘", "indicator": "软件工程师需求持续高位"},
            {"source": "教育部", "indicator": "软件工程专业新增博士点12个"},
        ], ensure_ascii=False),
        "avg_salary": "15-30万/年（本科起薪）",
        "demand_ratio": "2.5:1",
        "source": "招聘数据聚合",
        "period": "2024-2025",
    },
    {
        "major": "临床医学",
        "major_id": None,
        "industry": "医疗卫生",
        "trend": "持平",
        "confidence": 0.75,
        "signal_count": 2,
        "signals": json.dumps([
            {"source": "卫健委", "indicator": "执业医师数量稳步增长"},
            {"source": "医学院报告", "indicator": "规培制度持续严格执行"},
        ], ensure_ascii=False),
        "avg_salary": "10-20万/年（本科起薪，随职称增长）",
        "demand_ratio": "1.5:1",
        "source": "卫生统计年鉴",
        "period": "2024-2025",
    },
    {
        "major": "土木工程",
        "major_id": None,
        "industry": "建筑/房地产",
        "trend": "下行",
        "confidence": 0.90,
        "signal_count": 4,
        "signals": json.dumps([
            {"source": "国家统计局", "indicator": "房地产开发投资同比下降8%"},
            {"source": "行业协会", "indicator": "建筑企业新签合同额降幅扩大"},
            {"source": "高校", "indicator": "土木工程专业转出率上升"},
            {"source": "招聘数据", "indicator": "土建类岗位同比减少22%"},
        ], ensure_ascii=False),
        "avg_salary": "8-12万/年（本科起薪）",
        "demand_ratio": "0.6:1",
        "source": "多源综合",
        "period": "2024-2025",
    },
]

CORPUS_CHUNKS = [
    {
        "content": "张雪峰老师谈到高考志愿填报时强调：理科生选专业，首先要看这个专业有没有技术壁垒。计算机、医学、电子这些专业，你学四年出来，别人四年不学就干不了你的活儿，这就是壁垒。",
        "source": "直播回放-2024-03-15",
        "content_type": "直播转录",
        "date": "2024-03-15",
        "topic": "志愿填报",
        "stance": "技术壁垒论",
        "source_url": "",
        "chunk_index": 0,
        "metadata": {"keywords": "志愿填报,理科,技术壁垒,计算机,医学"},
    },
    {
        "content": "关于选大学还是选城市，张雪峰认为：能去一线城市读个普通一本，就别去三四线城市读个211。城市决定了你的眼界、实习机会和人脉圈层，大学四年在一个闭塞的地方，你对世界的认知会落后。",
        "source": "演讲-2023-09-10",
        "content_type": "演讲转录",
        "date": "2023-09-10",
        "topic": "择校策略",
        "stance": "城市优先论",
        "source_url": "",
        "chunk_index": 0,
        "metadata": {"keywords": "择校,城市,一线城市,眼界,实习"},
    },
    {
        "content": "土木工程这个专业，十年前那是黄金专业，各大设计院抢着要人。但是现在情况变了，房地产市场下行，基建增速放缓，土木的就业形势确实不如以前了。不过不是完全没有出路，市政工程、地下管廊、水利工程还有机会。",
        "source": "直播回放-2024-06-20",
        "content_type": "直播转录",
        "date": "2024-06-20",
        "topic": "专业分析",
        "stance": "谨慎乐观",
        "source_url": "",
        "chunk_index": 1,
        "metadata": {"keywords": "土木工程,就业,房地产,基建,行业下行"},
    },
    {
        "content": "学医这条路，张雪峰说得很直白：医学是上层家庭保底、下层家庭翻身的专业，但不是中层家庭的最优选择。因为学医周期太长，三十岁之前基本没有像样的收入，家庭条件一般的学生要扛住很大的经济压力。",
        "source": "演讲-2024-01-05",
        "content_type": "演讲转录",
        "date": "2024-01-05",
        "topic": "专业分析",
        "stance": "理性劝阻",
        "source_url": "",
        "chunk_index": 0,
        "metadata": {"keywords": "医学,家庭条件,学制,收入,翻身"},
    },
    {
        "content": "考砸了没关系，但你不能一直趴在地上。高考只是人生的一个节点，不是终点。我见过太多高考没考好但大学拼命学最后逆袭的例子，也见过太多考上清华最后毕业都费劲的例子。关键是你接下来怎么走。",
        "source": "直播回放-2024-06-08",
        "content_type": "直播转录",
        "date": "2024-06-08",
        "topic": "心理辅导",
        "stance": "鼓励",
        "source_url": "",
        "chunk_index": 0,
        "metadata": {"keywords": "考砸,心态,努力,逆袭,人生"},
    },
    {
        "content": "金融学这个专业，我可以负责任地告诉大家，如果你的家庭背景进不了前20%的富裕阶层，家里没有金融机构的人脉资源，那金融学对你来说就是一个普通的文科专业。清北复交的金融和普通学校的金融是两个概念。",
        "source": "演讲-2024-02-28",
        "content_type": "演讲转录",
        "date": "2024-02-28",
        "topic": "专业分析",
        "stance": "现实分析",
        "source_url": "",
        "chunk_index": 0,
        "metadata": {"keywords": "金融学,资源,人脉,院校差异,清北复交"},
    },
    {
        "content": "计算机科学与技术为什么这么多年一直热？因为它是所有理工科里最万金油的专业。你可以去互联网大厂写代码，可以去金融机构做量化，可以去制造业做信息化，甚至可以自己创业做SaaS。IT能力是现代社会的基础设施。",
        "source": "直播回放-2024-04-12",
        "content_type": "直播转录",
        "date": "2024-04-12",
        "topic": "专业分析",
        "stance": "积极推荐",
        "source_url": "",
        "chunk_index": 1,
        "metadata": {"keywords": "计算机,万金油,就业,互联网,IT"},
    },
    {
        "content": "英语专业现在确实遇到了挑战，AI翻译越来越准，单纯靠语言吃饭的岗位在萎缩。但是英语加任何其他专业技能，就是王炸。英语加法律做涉外法务，英语加金融做国际投行，英语加计算机做技术文档工程师。",
        "source": "直播回放-2024-05-18",
        "content_type": "直播转录",
        "date": "2024-05-18",
        "topic": "专业分析",
        "stance": "辩证分析",
        "source_url": "",
        "chunk_index": 2,
        "metadata": {"keywords": "英语,AI翻译,复合型,专业组合"},
    },
    {
        "content": "河南的高考生请注意：你们是全国最难的一批考生。分数线高、招生名额少、省内好大学少，这是客观事实。但正因为如此，河南考生更要精打细算地填志愿，每一个志愿都要物超所值。",
        "source": "演讲-2024-06-01",
        "content_type": "演讲转录",
        "date": "2024-06-01",
        "topic": "地域难度",
        "stance": "客观分析",
        "source_url": "",
        "chunk_index": 0,
        "metadata": {"keywords": "河南,高考,难度,志愿填报,分数线"},
    },
    {
        "content": "选择专业时有三个维度要考虑：兴趣、能力、就业。兴趣让你学得下去，能力让你学得好，就业让你学完了有饭吃。这三个里面如果非要排序，我会把就业放第一位，因为大多数人的兴趣是不稳定的，能力是可以培养的。",
        "source": "直播回放-2024-03-01",
        "content_type": "直播转录",
        "date": "2024-03-01",
        "topic": "志愿填报",
        "stance": "实用主义",
        "source_url": "",
        "chunk_index": 1,
        "metadata": {"keywords": "选专业,兴趣,能力,就业,三维度"},
    },
    {
        "content": "有些家长问我孩子要不要复读。我的标准很简单：如果是发挥失常，差了30分以上，可以复读；如果正常发挥但对学校和专业都不满意，可以复读。但如果已经发挥了正常水平，只是不甘心没有奇迹发生，那就别复读了，早一年进入社会比多读一年高三划算。",
        "source": "演讲-2024-06-25",
        "content_type": "演讲转录",
        "date": "2024-06-25",
        "topic": "复读决策",
        "stance": "理性分析",
        "source_url": "",
        "chunk_index": 0,
        "metadata": {"keywords": "复读,发挥失常,决策,时间成本"},
    },
    {
        "content": "考研择校这件事，我的建议是先选城市再选学校最后选导师。因为硕士就业时城市的影响力远大于学校排名，你在哪个城市读研，基本就决定了你第一份工作在哪里。导师反而是最关键的，跟对一个好导师比进一个名校有用得多。",
        "source": "直播回放-2024-02-15",
        "content_type": "直播转录",
        "date": "2024-02-15",
        "topic": "考研择校",
        "stance": "经验总结",
        "source_url": "",
        "chunk_index": 0,
        "metadata": {"keywords": "考研,择校,城市,导师,就业"},
    },
]


# =============================================================================
# Database insertion helpers
# =============================================================================

def seed_universities(conn: sqlite3.Connection) -> dict[str, int]:
    """Insert universities, return mapping of name -> id."""
    name_to_id: dict[str, int] = {}
    for u in UNIVERSITIES:
        cur = conn.execute(
            """INSERT INTO universities (name, province, city, tier, type, is_public)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (u["name"], u["province"], u["city"], u["tier"], u["type"], u["is_public"]),
        )
        name_to_id[u["name"]] = cur.lastrowid
    conn.commit()
    print(f"  [OK] Seeded {len(UNIVERSITIES)} universities")
    return name_to_id


def seed_majors(conn: sqlite3.Connection) -> dict[str, int]:
    """Insert majors, return mapping of name -> id."""
    name_to_id: dict[str, int] = {}
    for m in MAJORS:
        cur = conn.execute(
            """INSERT INTO majors (code, name, category, sub_category, barrier_level, description)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (m["code"], m["name"], m["category"], m["sub_category"],
             m["barrier_level"], m["description"]),
        )
        name_to_id[m["name"]] = cur.lastrowid
    conn.commit()
    print(f"  [OK] Seeded {len(MAJORS)} majors")
    return name_to_id


def seed_employment_trends(conn: sqlite3.Connection, major_ids: dict[str, int]) -> None:
    """Insert employment trends, linking to majors by ID."""
    count = 0
    for et in EMPLOYMENT_TRENDS:
        major_name = et["major"]
        major_id = major_ids.get(major_name)
        conn.execute(
            """INSERT INTO employment_trends
               (major, major_id, industry, trend, confidence, signal_count,
                signals, avg_salary, demand_ratio, source, period)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (et["major"], major_id, et["industry"], et["trend"],
             et["confidence"], et["signal_count"], et["signals"],
             et["avg_salary"], et["demand_ratio"], et["source"], et["period"]),
        )
        count += 1
    conn.commit()
    print(f"  [OK] Seeded {count} employment trends")


def seed_corpus_fts(conn: sqlite3.Connection) -> list[dict]:
    """Insert corpus chunks into FTS5 table. Returns chunk dicts for ChromaDB."""
    import jieba

    count = 0
    for i, chunk in enumerate(CORPUS_CHUNKS):
        # Pre-tokenize content with jieba so FTS5 unicode61 can index each word.
        # This mirrors the fts5_search() function that segments queries the same way.
        tokenized_content = " ".join(jieba.cut_for_search(chunk["content"]))
        conn.execute(
            """INSERT INTO corpus_fts (content, source, content_type, date, topic,
               stance, source_url, chunk_index)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (tokenized_content, chunk["source"], chunk["content_type"],
             chunk["date"], chunk["topic"], chunk["stance"],
             chunk["source_url"], chunk["chunk_index"]),
        )
        count += 1
    conn.commit()
    print(f"  [OK] Seeded {count} corpus chunks into FTS5")
    return CORPUS_CHUNKS


def seed_chroma_collection(chunks: list[dict], config: Config) -> None:
    """Insert corpus chunks into ChromaDB/NumpyCollection."""
    collection = get_chroma_collection(config)
    chunk_dicts = []
    for i, chunk in enumerate(chunks):
        chunk_id = f"seed-{uuid.uuid4().hex[:8]}"
        chunk_dicts.append({
            "id": chunk_id,
            "content": chunk["content"],
            "metadata": {
                "source": chunk["source"],
                "content_type": chunk["content_type"],
                "date": chunk["date"],
                "topic": chunk["topic"],
                "stance": chunk["stance"],
                "source_url": chunk["source_url"],
                "chunk_index": chunk["chunk_index"],
            },
        })
    add_chunks(collection, chunk_dicts)
    # Verification: query to confirm
    results = query_chunks(collection, "计算机志愿填报", top_k=3)
    print(f"  [OK] Seeded {len(chunk_dicts)} chunks into ChromaDB")
    print(f"  [OK] ChromaDB verification query returned {len(results)} hits")


# =============================================================================
# Verification
# =============================================================================

def verify_data(conn: sqlite3.Connection) -> None:
    """Run verification queries to confirm data integrity."""
    print("\n--- Data Verification ---")

    tables = ["universities", "majors", "employment_trends", "corpus_fts"]
    for table in tables:
        row = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()
        print(f"  {table}: {row['cnt']} rows")

    # Verify FTS5 search works
    results = fts5_search(conn, "计算机专业就业", limit=3)
    print(f"  FTS5 search '计算机专业就业': {len(results)} results")
    for r in results:
        print(f"    - topic={r.get('topic','')}, source={r.get('source','')}")

    # Verify employment trends
    trends = conn.execute(
        "SELECT major, trend, confidence FROM employment_trends"
    ).fetchall()
    for t in trends:
        print(f"  Trend: {t['major']} -> {t['trend']} (置信度:{t['confidence']})")


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Zhang Xuefeng Agent database")
    parser.add_argument(
        "--config", type=str, default=None,
        help="Path to .env or config file (optional)",
    )
    parser.add_argument(
        "--sqlite-path", type=str, default="data/zhangxuefeng.db",
        help="SQLite database path (default: data/zhangxuefeng.db)",
    )
    parser.add_argument(
        "--chroma-dir", type=str, default="data/chroma_db",
        help="ChromaDB persist directory (default: data/chroma_db)",
    )
    parser.add_argument(
        "--skip-chroma", action="store_true",
        help="Skip ChromaDB seeding (FTS5 only)",
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="Clear existing data before seeding",
    )
    args = parser.parse_args()

    # Build config
    config = load_config()
    config.sqlite_path = args.sqlite_path
    config.chroma_persist_dir = args.chroma_dir

    print("=" * 60)
    print("Zhang Xuefeng Agent - Seed Data Script")
    print(f"  SQLite: {config.sqlite_path}")
    print(f"  ChromaDB: {config.chroma_persist_dir}")
    print("=" * 60)

    # Initialize database
    conn = get_db(config)
    init_db(conn)

    # Clear existing data if requested
    if args.clear:
        print("\n--- Clearing existing data ---")
        conn.execute("DELETE FROM corpus_fts")
        conn.execute("DELETE FROM employment_trends")
        conn.execute("DELETE FROM major_university")
        conn.execute("DELETE FROM admission_scores")
        conn.execute("DELETE FROM majors")
        conn.execute("DELETE FROM universities")
        conn.commit()
        print("  [OK] All tables cleared")

    # Seed structured data
    print("\n--- Seeding Structured Data ---")
    university_ids = seed_universities(conn)
    major_ids = seed_majors(conn)
    seed_employment_trends(conn, major_ids)

    # Seed corpus (FTS5)
    print("\n--- Seeding Corpus Data ---")
    chunks = seed_corpus_fts(conn)

    # Seed ChromaDB
    if not args.skip_chroma:
        print("\n--- Seeding ChromaDB ---")
        seed_chroma_collection(chunks, config)

    # Verify
    verify_data(conn)

    conn.close()
    print("\n[DONE] Seed data import completed successfully.")


if __name__ == "__main__":
    main()
