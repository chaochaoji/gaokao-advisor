"""Smoke tests for project skeleton."""


def test_sample_config_import(sample_config):
    """Verify that Config can be instantiated from conftest fixture."""
    assert sample_config.llm_primary_api_key == "test-key-primary"
    assert sample_config.llm_fallback_api_key == "test-key-fallback"
    assert sample_config.embedding_api_key == "test-embed-key"
    assert sample_config.chroma_persist_dir == ":memory:"
    assert sample_config.sqlite_path == ":memory:"
