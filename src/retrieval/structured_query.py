"""Structured (SQL) query module — queries FTS5 corpus for score/position data."""

from __future__ import annotations
import sqlite3, re


def query_admission(
    db_conn: sqlite3.Connection,
    province: str,
    year: int,
    category: str,
    min_score: int,
    max_score: int | None = None,
) -> list[dict]:
    """Search FTS5 corpus for admission score-position-university data.

    Looks in corpus_fts for chunks matching the province + score range.
    """
    if max_score is None:
        max_score = min_score + 50

    # category mapping: normalize user input
    cat_map = {
        "物理": "物理", "物理类": "物理", "physics": "物理",
        "历史": "历史", "历史类": "历史", "history": "历史",
        "综合": "综合", "comprehensive": "综合",
    }
    cat = cat_map.get(category, category)

    results = []
    try:
        # Search FTS5 for province + year hints
        cursor = db_conn.execute(
            "SELECT content, source, rowid FROM corpus_fts "
            "WHERE (source LIKE ? OR content LIKE ?) AND content_type = 'score_data' "
            "ORDER BY rowid ASC LIMIT 100",
            (f"%{province}%", f"%{province}%")
        )
        rows = cursor.fetchall()
        if not rows:
            # Fallback: search broader
            cursor = db_conn.execute(
                "SELECT content, source, rowid FROM corpus_fts "
                "WHERE (content LIKE ? OR content LIKE ?) ORDER BY rowid ASC LIMIT 50",
                (f"%{province}%{year}%", f"%{province}%")
            )
            rows = cursor.fetchall()

        for content, source, rowid in rows:
            # Filter: look for score-position lines matching the range
            lines = content.split('\n')
            matched = []
            for line in lines:
                # Match lines like "580分 | 位次12000 | 太原理工大学"
                m = re.search(r'(\d{3})\s*分\s*[|｜]\s*位次\s*(\d{3,7})\s*[|｜]\s*(.+)', line)
                if m:
                    score = int(m.group(1))
                    if min_score <= score <= max_score:
                        matched.append(line.strip())
            if matched:
                results.append({
                    "content": f"[{province} {year}年 {cat}] 分数区间 {min_score}-{max_score}:\n" + "\n".join(matched[:20]),
                    "source": f"{source}",
                    "content_type": "score_data",
                })
    except Exception:
        pass

    return results


def query_employment(db_conn: sqlite3.Connection, major: str) -> list[dict]:
    """Search FTS5 corpus for employment/major prospect data."""
    try:
        cursor = db_conn.execute(
            "SELECT content, source FROM corpus_fts WHERE content LIKE ? LIMIT 10",
            (f"%{major}%",)
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []


def query_city_clusters(db_conn: sqlite3.Connection, city_or_cluster: str) -> list[dict]:
    """Search FTS5 corpus for city/industry cluster data."""
    try:
        cursor = db_conn.execute(
            "SELECT content, source FROM corpus_fts WHERE content LIKE ? LIMIT 10",
            (f"%{city_or_cluster}%",)
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []


def query_major_requirements(db_conn, major_name, province, year):
    """Search FTS5 corpus for major selection requirements."""
    try:
        cursor = db_conn.execute(
            "SELECT content, source FROM corpus_fts "
            "WHERE (content LIKE ? AND content LIKE ?) LIMIT 10",
            (f"%{major_name}%", f"%{province}%")
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []
