import pytest
import tempfile
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def sample_config():
    from config import Config
    return Config(
        llm_primary_api_key="test-key-primary",
        llm_fallback_api_key="test-key-fallback",
        embedding_api_key="test-embed-key",
        embedding_mode="api",
        reranker_mode="api",
        chroma_persist_dir=":memory:",
        sqlite_path=":memory:",
    )
