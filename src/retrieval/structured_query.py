"""Structured (SQL) query module for the evidence layer.

Provides domain-specific query functions that join the normalized
tables (universities, admission_scores, majors, employment_trends,
city_industries, major_selection_requirements) and return dict lists
suitable for downstream consumers.
"""

from __future__ import annotations

import sqlite3


def query_admission(
    db_conn: sqlite3.Connection,
    province: str,
    year: int,
    category: str,
    min_score: int,
    max_score: int | None = None,
) -> list[dict]:
    """Look up admission scores within a score band.

    Parameters
    ----------
    db_conn : sqlite3.Connection
        Open SQLite connection.
    province : str
        Target province (e.g. ``"浙江"``).
    year : int
        Admission year (e.g. 2024).
    category : str
        Exam category (e.g. ``"物理类"``, ``"历史类"``).
    min_score : int
        Lower bound (inclusive) of the score band.
    max_score : int or None
        Upper bound (inclusive).  Defaults to *min_score* + 50 when
        omitted.

    Returns
    -------
    list[dict]
        Rows with keys: ``university``, plus all columns from
        ``admission_scores`` (``id``, ``university_id``, ``province``,
        ``year``, ``category``, ``selection_combo``, ``batch``,
        ``min_score``, ``min_rank``, ``major``, ``source``, ``updated_at``).
    """
    if max_score is None:
        max_score = min_score + 50

    cursor = db_conn.execute(
        """SELECT u.name AS university, a.*
           FROM admission_scores a
           JOIN universities u ON a.university_id = u.id
           WHERE a.province = ? AND a.year = ? AND a.category = ?
             AND a.min_score BETWEEN ? AND ?
           ORDER BY a.min_score DESC""",
        (province, year, category, min_score, max_score),
    )
    return [dict(row) for row in cursor.fetchall()]


def query_employment(db_conn: sqlite3.Connection, major: str) -> list[dict]:
    """Query employment trends for a major (fuzzy match).

    Parameters
    ----------
    db_conn : sqlite3.Connection
        Open SQLite connection.
    major : str
        Major name or partial name (``LIKE %major%``).

    Returns
    -------
    list[dict]
        Matching rows from ``employment_trends``.
    """
    cursor = db_conn.execute(
        "SELECT * FROM employment_trends WHERE major LIKE ?",
        (f"%{major}%",),
    )
    return [dict(row) for row in cursor.fetchall()]


def query_city_clusters(
    db_conn: sqlite3.Connection, city_or_cluster: str
) -> list[dict]:
    """Query city-industry clusters for a city or cluster name.

    Parameters
    ----------
    db_conn : sqlite3.Connection
        Open SQLite connection.
    city_or_cluster : str
        City name or industry cluster keyword (``LIKE`` on both columns).

    Returns
    -------
    list[dict]
        Matching rows from ``city_industries``.
    """
    cursor = db_conn.execute(
        "SELECT * FROM city_industries WHERE city LIKE ? OR cluster LIKE ?",
        (f"%{city_or_cluster}%", f"%{city_or_cluster}%"),
    )
    return [dict(row) for row in cursor.fetchall()]


def query_major_requirements(
    db_conn: sqlite3.Connection,
    major_name: str,
    province: str,
    year: int,
) -> list[dict]:
    """Query subject-selection requirements for a major in a province/year.

    Parameters
    ----------
    db_conn : sqlite3.Connection
        Open SQLite connection.
    major_name : str
        Major name or partial name (``LIKE %major_name%``).
    province : str
        Target province.
    year : int
        Target year.

    Returns
    -------
    list[dict]
        Rows with keys: all columns from ``major_selection_requirements``
        plus ``major_name`` from the ``majors`` table.
    """
    cursor = db_conn.execute(
        """SELECT mr.*, m.name AS major_name
           FROM major_selection_requirements mr
           JOIN majors m ON mr.major_id = m.id
           WHERE m.name LIKE ? AND mr.province = ? AND mr.year = ?""",
        (f"%{major_name}%", province, year),
    )
    return [dict(row) for row in cursor.fetchall()]
