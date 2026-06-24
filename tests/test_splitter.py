from src.data.splitter import GaokaoTextSplitter


def test_qa_boundary_preserved():
    splitter = GaokaoTextSplitter()
    text = "问：计算机怎么样？答：计算机要看城市。问：那师范呢？答：师范要看编制。"
    chunks = splitter.split_text(text, "live_transcript", {})
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk["content"].count("问：") <= 2  # QA对完整


def test_article_split_by_headings():
    splitter = GaokaoTextSplitter()
    text = "## 计算机专业\n很多内容...\n## 医学专业\n更多内容..."
    chunks = splitter.split_text(text, "article", {})
    assert len(chunks) >= 2


def test_metadata_injection():
    splitter = GaokaoTextSplitter()
    chunks = splitter.split_text("测试内容" * 50, "social_post", {"source": "公众号"})
    for c in chunks:
        assert c["metadata"]["source"] == "公众号"
