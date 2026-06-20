"""Tests for configuration management module."""

import os
import pytest
from config import Config, load_config


class TestConfigDefaults:
    """Verify default values for all Config fields."""

    # ── LLM fields ──
    def test_default_llm_models(self):
        config = Config()
        assert config.llm_primary_model == "claude-sonnet-4-6"
        assert config.llm_fallback_model == "deepseek-chat"

    def test_default_llm_api_keys(self):
        config = Config()
        assert config.llm_primary_api_key == ""
        assert config.llm_fallback_api_key == ""

    def test_default_llm_base_urls(self):
        config = Config()
        assert config.llm_primary_base_url == "https://api.anthropic.com"
        assert config.llm_fallback_base_url == "https://api.deepseek.com/v1"

    def test_default_llm_timeout(self):
        config = Config()
        assert config.llm_timeout == 30

    # ── Embedding fields ──
    def test_default_embedding(self):
        config = Config()
        assert config.embedding_mode == "api"
        assert config.embedding_api_key == ""
        assert config.embedding_model == "BAAI/bge-m3"
        assert config.embedding_local_path == "models/bge-m3"

    # ── Reranker fields ──
    def test_default_reranker(self):
        config = Config()
        assert config.reranker_mode == "api"
        assert config.reranker_model == "BAAI/bge-reranker-v2-m3"

    # ── Storage fields ──
    def test_default_storage(self):
        config = Config()
        assert config.chroma_persist_dir == "data/chroma_db"
        assert config.sqlite_path == "data/zhangxuefeng.db"

    # ── UI fields ──
    def test_default_gradio_port(self):
        config = Config()
        assert config.gradio_port == 7860

    def test_default_gradio_share(self):
        config = Config()
        assert config.gradio_share is False

    # ── Limits fields ──
    def test_default_limits(self):
        config = Config()
        assert config.max_concurrent_requests == 10
        assert config.rate_limit_per_user == 2

    # ── Logging fields ──
    def test_default_logging(self):
        config = Config()
        assert config.log_dir == "logs"
        assert config.log_level == "INFO"
        assert config.log_retention_days == 30


class TestLoadConfig:
    """Verify load_config() and environment variable override behaviour."""

    def test_no_env_vars_uses_all_defaults(self):
        """When no ZXF_* vars are set, load_config returns a Config with defaults."""
        config = load_config()
        assert config.llm_primary_model == "claude-sonnet-4-6"
        assert config.llm_timeout == 30
        assert config.gradio_port == 7860
        assert config.embedding_mode == "api"

    # ── String overrides ──
    def test_env_var_override_string(self, monkeypatch):
        monkeypatch.setenv("ZXF_LLM_PRIMARY_MODEL", "claude-opus-4-8")
        monkeypatch.setenv("ZXF_LLM_FALLBACK_MODEL", "gpt-4o")
        monkeypatch.setenv("ZXF_EMBEDDING_MODE", "local")
        config = load_config()
        assert config.llm_primary_model == "claude-opus-4-8"
        assert config.llm_fallback_model == "gpt-4o"
        assert config.embedding_mode == "local"

    def test_env_var_override_api_keys(self, monkeypatch):
        monkeypatch.setenv("ZXF_LLM_PRIMARY_API_KEY", "sk-primary-123")
        monkeypatch.setenv("ZXF_LLM_FALLBACK_API_KEY", "sk-fallback-456")
        monkeypatch.setenv("ZXF_EMBEDDING_API_KEY", "sk-embed-789")
        config = load_config()
        assert config.llm_primary_api_key == "sk-primary-123"
        assert config.llm_fallback_api_key == "sk-fallback-456"
        assert config.embedding_api_key == "sk-embed-789"

    def test_env_var_override_base_urls(self, monkeypatch):
        monkeypatch.setenv("ZXF_LLM_PRIMARY_BASE_URL", "https://custom.api.com")
        monkeypatch.setenv("ZXF_LLM_FALLBACK_BASE_URL", "https://fallback.api.com")
        config = load_config()
        assert config.llm_primary_base_url == "https://custom.api.com"
        assert config.llm_fallback_base_url == "https://fallback.api.com"

    # ── Integer overrides ──
    def test_env_var_override_int(self, monkeypatch):
        monkeypatch.setenv("ZXF_LLM_TIMEOUT", "60")
        monkeypatch.setenv("ZXF_GRADIO_PORT", "9999")
        monkeypatch.setenv("ZXF_MAX_CONCURRENT_REQUESTS", "5")
        monkeypatch.setenv("ZXF_RATE_LIMIT_PER_USER", "10")
        monkeypatch.setenv("ZXF_LOG_RETENTION_DAYS", "90")
        config = load_config()
        assert config.llm_timeout == 60
        assert config.gradio_port == 9999
        assert config.max_concurrent_requests == 5
        assert config.rate_limit_per_user == 10
        assert config.log_retention_days == 90

    # ── Boolean overrides ──
    @pytest.mark.parametrize("env_val, expected", [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("False", False),
        ("0", False),
        ("no", False),
    ])
    def test_env_var_override_bool(self, monkeypatch, env_val, expected):
        monkeypatch.setenv("ZXF_GRADIO_SHARE", env_val)
        config = load_config()
        assert config.gradio_share == expected

    # ── Reranker / Embedding / Storage / Logging overrides ──
    def test_env_var_override_reranker(self, monkeypatch):
        monkeypatch.setenv("ZXF_RERANKER_MODE", "local")
        monkeypatch.setenv("ZXF_RERANKER_MODEL", "custom/reranker")
        config = load_config()
        assert config.reranker_mode == "local"
        assert config.reranker_model == "custom/reranker"

    def test_env_var_override_embedding_model_path(self, monkeypatch):
        monkeypatch.setenv("ZXF_EMBEDDING_MODEL", "custom/embed-model")
        monkeypatch.setenv("ZXF_EMBEDDING_LOCAL_PATH", "/opt/models/embed")
        config = load_config()
        assert config.embedding_model == "custom/embed-model"
        assert config.embedding_local_path == "/opt/models/embed"

    def test_env_var_override_storage(self, monkeypatch):
        monkeypatch.setenv("ZXF_CHROMA_PERSIST_DIR", "/data/chroma")
        monkeypatch.setenv("ZXF_SQLITE_PATH", "/data/custom.db")
        config = load_config()
        assert config.chroma_persist_dir == "/data/chroma"
        assert config.sqlite_path == "/data/custom.db"

    def test_env_var_override_logging(self, monkeypatch):
        monkeypatch.setenv("ZXF_LOG_DIR", "/var/log/zxf")
        monkeypatch.setenv("ZXF_LOG_LEVEL", "DEBUG")
        config = load_config()
        assert config.log_dir == "/var/log/zxf"
        assert config.log_level == "DEBUG"

    def test_env_var_not_set_uses_default(self):
        """Fields without ZXF_ env vars keep their defaults."""
        # Ensure no relevant env vars are set (run in clean env)
        config = load_config()
        assert config.llm_timeout == 30
        assert config.embedding_mode == "api"
