"""Application configuration module."""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Central configuration for the Zhang Xuefeng Knowledge Agent.

    All fields have sensible defaults.  Every field can be overridden
    at runtime via a ZXF_<FIELD_NAME_UPPER> environment variable (see
    :func:`load_config`).
    """

    # ── LLM ──────────────────────────────────────────────────────────
    llm_primary_model: str = "claude-sonnet-4-6"
    llm_primary_api_key: str = ""
    llm_primary_base_url: str = "https://api.anthropic.com"
    llm_fallback_model: str = "deepseek-chat"
    llm_fallback_api_key: str = ""
    llm_fallback_base_url: str = "https://api.deepseek.com/v1"
    llm_timeout: int = 30

    # ── Embedding ────────────────────────────────────────────────────
    embedding_mode: str = "api"
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-m3"
    embedding_local_path: str = "models/bge-m3"

    # ── Reranker ─────────────────────────────────────────────────────
    reranker_mode: str = "api"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # ── Storage ──────────────────────────────────────────────────────
    chroma_persist_dir: str = "data/chroma_db"
    sqlite_path: str = "data/zhangxuefeng.db"

    # ── UI ───────────────────────────────────────────────────────────
    gradio_port: int = 7860
    gradio_share: bool = False

    # ── Limits ───────────────────────────────────────────────────────
    max_concurrent_requests: int = 10
    rate_limit_per_user: int = 2

    # ── Logging ──────────────────────────────────────────────────────
    log_dir: str = "logs"
    log_level: str = "INFO"
    log_retention_days: int = 30


def load_config() -> Config:
    """Build a :class:`Config` from defaults, overridden by environment.

    Environment variables use the ``ZXF_`` prefix followed by the
    uppercase field name.  Values are coerced to the field's type
    (``bool``, ``int``, or kept as ``str``).

    Returns
    -------
    Config
        Fully resolved configuration object.
    """
    config = Config()
    for field_name in Config.__dataclass_fields__:
        env_key = f"ZXF_{field_name.upper()}"
        env_val = os.getenv(env_key)
        if env_val is not None:
            field_type = type(getattr(Config, field_name))
            if field_type == bool:
                setattr(config, field_name, env_val.lower() in ("true", "1", "yes"))
            elif field_type == int:
                setattr(config, field_name, int(env_val))
            else:
                setattr(config, field_name, env_val)
    return config
