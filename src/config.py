"""Application configuration module."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Central configuration for the Zhang Xuefeng Knowledge Agent."""

    llm_primary_api_key: str
    llm_primary_model: str = "claude-sonnet-4-6"
    llm_fallback_api_key: Optional[str] = None
    llm_fallback_model: str = "deepseek-chat"
    embedding_api_key: Optional[str] = None
    embedding_mode: str = "api"
    reranker_api_key: Optional[str] = None
    reranker_mode: str = "api"
    chroma_persist_dir: str = "./data/chroma_db"
    sqlite_path: str = "./data/zxf.db"
    gradio_port: int = 7860
    data_raw_dir: str = "./data/raw"
    data_processed_dir: str = "./data/processed"
    logs_dir: str = "./logs"
    models_dir: str = "./models"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        import os

        return cls(
            llm_primary_api_key=os.getenv("ZXF_LLM_PRIMARY_API_KEY", ""),
            llm_primary_model=os.getenv("ZXF_LLM_PRIMARY_MODEL", "claude-sonnet-4-6"),
            llm_fallback_api_key=os.getenv("ZXF_LLM_FALLBACK_API_KEY"),
            llm_fallback_model=os.getenv("ZXF_LLM_FALLBACK_MODEL", "deepseek-chat"),
            embedding_api_key=os.getenv("ZXF_EMBEDDING_API_KEY"),
            embedding_mode=os.getenv("ZXF_EMBEDDING_MODE", "api"),
            gradio_port=int(os.getenv("GRADIO_PORT", "7860")),
        )
