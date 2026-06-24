"""Application configuration module."""

import os
from dataclasses import dataclass
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _load_dotenv_if_available() -> None:
    if not _ENV_FILE.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(_ENV_FILE)
    except ImportError:
        pass


@dataclass
class Config:
    """Central configuration for GaokaoGuide.

    All fields have sensible defaults.  Every field can be overridden
    at runtime via a ZXF_<FIELD_NAME_UPPER> environment variable (see
    :func:`load_config`).
    """

    # ── LLM ──────────────────────────────────────────────────────────
    llm_primary_model: str = "claude-sonnet-4-6"
    llm_primary_api_key: str = ""
    llm_primary_base_url: str = "https://api.anthropic.com"
    llm_primary_api_type: str = "auto"   # "anthropic" | "openai" | "auto"
    llm_fallback_model: str = "deepseek-chat"
    llm_fallback_api_key: str = ""
    llm_fallback_base_url: str = "https://api.deepseek.com/v1"
    llm_fallback_api_type: str = "auto"  # "anthropic" | "openai" | "auto"
    llm_timeout: int = 120

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
    sqlite_path: str = "data/gaokao.db"

    # ── UI ───────────────────────────────────────────────────────────
    gradio_port: int = 7860
    gradio_share: bool = False

    # ── Logging ──────────────────────────────────────────────────────
    log_dir: str = "logs"
    log_level: str = "INFO"


def load_config(load_env_file: bool = True) -> Config:
    """Build a :class:`Config` from defaults, overridden by environment.

    When *load_env_file* is true (the default), ``.env`` in the project
    root is loaded into ``os.environ`` first.

    Returns
    -------
    Config
        Fully resolved configuration object.
    """
    if load_env_file:
        _load_dotenv_if_available()

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
