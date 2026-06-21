"""Shared service instances for the FastAPI application."""
from __future__ import annotations

import os, sys
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SRC_ROOT = os.path.join(_PROJECT_ROOT, "src")
if _PROJECT_ROOT not in sys.path: sys.path.insert(0, _PROJECT_ROOT)
if _SRC_ROOT not in sys.path: sys.path.insert(0, _SRC_ROOT)

from src.config import load_config
from src.knowledge.sqlite_store import get_db, init_db
from src.knowledge.chroma_store import get_chroma_collection
from src.knowledge.session_store import SessionStore
from src.retrieval.embedding_service import EmbeddingService
from src.retrieval.reranker import RerankerService
from src.retrieval.hybrid_search import HybridSearch
from src.safety.input_gateway import InputSafetyGateway
from src.utils.logger import AgentLogger

config = load_config()
logger = AgentLogger(config.log_dir, session_id="api")

db = get_db(config)
init_db(db)
logger.log_info("sqlite", "db_initialized", {"path": config.sqlite_path})

session_store = SessionStore(db)
logger.log_info("sqlite", "session_store_initialized")

chroma_col = get_chroma_collection(config)
logger.log_info("chromadb", "collection_loaded")

embedding_svc = EmbeddingService(
    mode=config.embedding_mode, api_key=config.embedding_api_key,
    model=config.embedding_model, local_path=config.embedding_local_path)
logger.log_info("embedding", "service_initialized", {"mode": embedding_svc.mode, "device": embedding_svc.device_info})

reranker = RerankerService(mode=config.reranker_mode, model=config.reranker_model)
logger.log_info("reranker", "service_initialized", {"mode": config.reranker_mode})

hybrid_search = HybridSearch(
    mode="prod", embedding_svc=embedding_svc, chroma_col=chroma_col,
    db_conn=db, reranker=reranker, logger=logger)
logger.log_info("hybrid_search", "service_initialized")

safety = InputSafetyGateway()
logger.log_info("safety", "gateway_initialized")
