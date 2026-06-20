"""Tests for vector_search, keyword_search, and structured_query modules."""

import pytest
import sqlite3


# -- Fixtures ---------------------------------------------------------------


@pytest.fixture
def chroma_col_empty():
    """An empty NumpyCollection (no persistence, no embedding service)."""
    from src.knowledge.chroma_store import NumpyCollection
    return NumpyCollection(name="test_empty", embedding_dim=64)


@pytest.fixture
def chroma_col_with_data():
    """A NumpyCollection pre-populated with two documents."""
    from src.knowledge.chroma_store import NumpyCollection
    col = NumpyCollection(name="test_data", embedding_dim=64)
    col.add(
        ids=["doc-1", "doc-2"],
        documents=["computer science has great prospects", "finance needs versatile talent"],
        metadatas=[
            {"source": "live", "topic": "cs"},
            {"source": "article", "topic": "finance"},
        ],
    )
    return col


@pytest.fixture
def db_conn():
    """In-memory SQLite db with full schema and sample evidence/corpus data."""
    from src.knowledge.sqlite_store import init_db
    import jieba

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)

    # Seed universities
    conn.execute(
        "INSERT INTO universities (name, province, city, tier, type) "
        "VALUES ('Zhejiang University', 'Zhejiang', 'Hangzhou', '985', 'comprehensive')"
    )
    conn.execute(
        "INSERT INTO universities (name, province, city, tier, type) "
        "VALUES ('Hangzhou Dianzi University', 'Zhejiang', 'Hangzhou', 'normal', 'engineering')"
    )
    conn.execute(
        "INSERT INTO universities (name, province, city, tier, type) "
        "VALUES ('Peking University', 'Beijing', 'Beijing', '985', 'comprehensive')"
    )

    # Seed admission_scores
    conn.execute(
        "INSERT INTO admission_scores "
        "(university_id, province, year, category, batch, min_score, min_rank, major) "
        "VALUES (1, 'Zhejiang', 2024, 'physics', 'batch1', 665, 4500, 'Computer Science')"
    )
    conn.execute(
        "INSERT INTO admission_scores "
        "(university_id, province, year, category, batch, min_score, min_rank, major) "
        "VALUES (2, 'Zhejiang', 2024, 'physics', 'batch1', 610, 12000, 'Software Engineering')"
    )
    conn.execute(
        "INSERT INTO admission_scores "
        "(university_id, province, year, category, batch, min_score, min_rank, major) "
        "VALUES (3, 'Beijing', 2024, 'physics', 'batch1', 690, 800, 'Computer Science')"
    )

    # Seed majors
    conn.execute(
        "INSERT INTO majors (name, category, sub_category, barrier_level) "
        "VALUES ('Computer Science', 'engineering', 'cs', 'high')"
    )
    conn.execute(
        "INSERT INTO majors (name, category, sub_category, barrier_level) "
        "VALUES ('Finance', 'economics', 'finance', 'medium')"
    )

    # Seed employment_trends
    conn.execute(
        "INSERT INTO employment_trends (major, industry, trend, confidence) "
        "VALUES ('Computer Science', 'IT', 'rising', 0.85)"
    )
    conn.execute(
        "INSERT INTO employment_trends (major, industry, trend, confidence) "
        "VALUES ('Finance', 'Banking', 'flat', 0.60)"
    )

    # Seed city_industries
    conn.execute(
        "INSERT INTO city_industries (city, province, cluster, scale, major_companies) "
        "VALUES ('Hangzhou', 'Zhejiang', 'Internet/Tech', 'large', 'Alibaba, NetEase')"
    )
    conn.execute(
        "INSERT INTO city_industries (city, province, cluster, scale, major_companies) "
        "VALUES ('Shenzhen', 'Guangdong', 'Hardware/Tech', 'large', 'Huawei, Tencent')"
    )

    # Seed major_selection_requirements
    conn.execute(
        "INSERT INTO major_selection_requirements "
        "(major_id, province, year, required_subjects, optional_subjects) "
        "VALUES (1, 'Zhejiang', 2024, 'Physics', 'Chemistry,Biology')"
    )
    conn.execute(
        "INSERT INTO major_selection_requirements "
        "(major_id, province, year, required_subjects, optional_subjects) "
        "VALUES (1, 'Beijing', 2024, 'Physics', 'Chemistry')"
    )

    # Seed corpus_fts with pre-tokenized content
    tokenized = " ".join(jieba.cut_for_search("computer science major career prospects"))
    conn.execute(
        "INSERT INTO corpus_fts (content, source, content_type, date, topic) "
        "VALUES (?, ?, ?, ?, ?)",
        (tokenized, "live_stream", "transcript", "2024-03-15", "cs"),
    )

    conn.commit()
    yield conn
    conn.close()


# -- Vector Search Tests ----------------------------------------------------


class TestVectorSearch:
    """Tests for vector_search()."""

    def test_empty_collection_returns_empty(self, chroma_col_empty):
        from src.retrieval.vector_search import vector_search
        results = vector_search(None, chroma_col_empty, "any query", top_k=5)
        assert results == []

    def test_returns_results_with_score(self, chroma_col_with_data):
        from src.retrieval.vector_search import vector_search
        results = vector_search(None, chroma_col_with_data, "computer science", top_k=2)
        assert len(results) == 2
        for r in results:
            assert "id" in r
            assert "content" in r
            assert "metadata" in r
            assert "score" in r
            assert 0.0 <= r["score"] <= 1.0

    def test_top_k_limits_results(self, chroma_col_with_data):
        from src.retrieval.vector_search import vector_search
        results = vector_search(None, chroma_col_with_data, "finance", top_k=1)
        assert len(results) == 1

    def test_score_is_one_minus_distance(self, chroma_col_with_data):
        from src.retrieval.vector_search import vector_search
        results = vector_search(None, chroma_col_with_data, "test", top_k=2)
        raw = chroma_col_with_data.query(
            query_texts=["test"], n_results=2,
            include=["documents", "metadatas", "distances"],
        )
        for i, r in enumerate(results):
            expected_score = 1.0 - raw["distances"][0][i]
            assert abs(r["score"] - expected_score) < 0.0001


# -- Keyword Search Tests ---------------------------------------------------


class TestKeywordSearch:
    """Tests for keyword_search()."""

    def test_matching_keyword_returns_rows(self, db_conn):
        from src.retrieval.keyword_search import keyword_search
        results = keyword_search(db_conn, "computer", top_k=5)
        assert len(results) > 0
        assert "content" in results[0]
        assert "source" in results[0]

    def test_no_match_returns_empty(self, db_conn):
        from src.retrieval.keyword_search import keyword_search
        results = keyword_search(db_conn, "xyznonexistent999", top_k=5)
        assert results == []

    def test_limit_respected(self, db_conn):
        from src.retrieval.keyword_search import keyword_search
        results = keyword_search(db_conn, "computer", top_k=1)
        assert len(results) <= 1


# -- Structured Query Tests ------------------------------------------------


class TestQueryAdmission:
    """Tests for query_admission()."""

    def test_exact_match_province_year_category(self, db_conn):
        from src.retrieval.structured_query import query_admission
        # Use a wide score band to catch both Zhejiang admissions (610 and 665)
        results = query_admission(db_conn, "Zhejiang", 2024, "physics", 600, 670)
        assert len(results) == 2
        for r in results:
            assert r["province"] == "Zhejiang"
            assert r["year"] == 2024
            assert r["category"] == "physics"

    def test_score_band_filtering(self, db_conn):
        from src.retrieval.structured_query import query_admission
        results = query_admission(db_conn, "Zhejiang", 2024, "physics", 660, 670)
        assert len(results) == 1
        assert results[0]["university"] == "Zhejiang University"
        assert 660 <= results[0]["min_score"] <= 670

    def test_default_max_score_is_min_plus_50(self, db_conn):
        from src.retrieval.structured_query import query_admission
        # min_score=600 -> default band 600-650, catches Hangzhou Dianzi (610)
        results = query_admission(db_conn, "Zhejiang", 2024, "physics", 600)
        assert len(results) == 1
        for r in results:
            assert 600 <= r["min_score"] <= 650

    def test_no_match_returns_empty(self, db_conn):
        from src.retrieval.structured_query import query_admission
        results = query_admission(db_conn, "Zhejiang", 2024, "physics", 400, 450)
        assert results == []


class TestQueryEmployment:
    """Tests for query_employment()."""

    def test_exact_major_match(self, db_conn):
        from src.retrieval.structured_query import query_employment
        results = query_employment(db_conn, "Computer Science")
        assert len(results) == 1
        assert results[0]["major"] == "Computer Science"
        assert results[0]["trend"] == "rising"

    def test_partial_major_match(self, db_conn):
        from src.retrieval.structured_query import query_employment
        results = query_employment(db_conn, "Computer")
        assert len(results) == 1
        assert "Computer Science" in results[0]["major"]

    def test_no_match_returns_empty(self, db_conn):
        from src.retrieval.structured_query import query_employment
        results = query_employment(db_conn, "Astrophysics")
        assert results == []


class TestQueryCityClusters:
    """Tests for query_city_clusters()."""

    def test_exact_city_match(self, db_conn):
        from src.retrieval.structured_query import query_city_clusters
        results = query_city_clusters(db_conn, "Hangzhou")
        assert len(results) == 1
        assert results[0]["city"] == "Hangzhou"
        assert results[0]["cluster"] == "Internet/Tech"

    def test_cluster_keyword_match(self, db_conn):
        from src.retrieval.structured_query import query_city_clusters
        results = query_city_clusters(db_conn, "Tech")
        assert len(results) >= 2

    def test_no_match_returns_empty(self, db_conn):
        from src.retrieval.structured_query import query_city_clusters
        results = query_city_clusters(db_conn, "Atlantis")
        assert results == []


class TestQueryMajorRequirements:
    """Tests for query_major_requirements()."""

    def test_exact_match(self, db_conn):
        from src.retrieval.structured_query import query_major_requirements
        results = query_major_requirements(db_conn, "Computer Science", "Zhejiang", 2024)
        assert len(results) == 1
        assert results[0]["major_name"] == "Computer Science"
        assert results[0]["required_subjects"] == "Physics"
        assert results[0]["province"] == "Zhejiang"
        assert results[0]["year"] == 2024

    def test_partial_name_match(self, db_conn):
        from src.retrieval.structured_query import query_major_requirements
        results = query_major_requirements(db_conn, "Computer", "Zhejiang", 2024)
        assert len(results) == 1
        assert "Computer Science" in results[0]["major_name"]

    def test_different_province_different_requirements(self, db_conn):
        from src.retrieval.structured_query import query_major_requirements
        zj = query_major_requirements(db_conn, "Computer Science", "Zhejiang", 2024)
        bj = query_major_requirements(db_conn, "Computer Science", "Beijing", 2024)
        assert len(zj) == 1
        assert len(bj) == 1
        assert zj[0]["optional_subjects"] != bj[0]["optional_subjects"]

    def test_no_match_returns_empty(self, db_conn):
        from src.retrieval.structured_query import query_major_requirements
        results = query_major_requirements(db_conn, "Astrophysics", "Zhejiang", 2024)
        assert results == []
