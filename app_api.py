# -*- coding: utf-8 -*-
"""GaokaoGuide — AI-powered college admission advisor."""
from __future__ import annotations
import os, sys
from contextlib import asynccontextmanager

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC_ROOT = os.path.join(_PROJECT_ROOT, "src")
if _PROJECT_ROOT not in sys.path: sys.path.insert(0, _PROJECT_ROOT)
if _SRC_ROOT not in sys.path: sys.path.insert(0, _SRC_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.api.dependencies import config, logger, db, session_store, chroma_col, embedding_svc, reranker, hybrid_search, safety

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.log_info("api", "server_starting", {"port": config.gradio_port})
    yield
    logger.log_info("api", "server_stopped")

app = FastAPI(title="GaokaoGuide", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/api/health")
def health():
    status = {}
    try:
        db.execute("SELECT 1")
        status["database"] = "healthy"
    except Exception as e:
        status["database"] = f"unhealthy: {e}"
    try:
        count = len(chroma_col._ids) if hasattr(chroma_col, "_ids") else "?"
        status["knowledge_base"] = f"healthy ({count} docs)"
    except Exception as e:
        status["knowledge_base"] = f"unhealthy: {e}"
    status["embedding"] = f"healthy ({embedding_svc.mode}, {embedding_svc.device_info})"
    status["reranker"] = f"healthy (mode={config.reranker_mode})"
    try:
        sessions = session_store.list_sessions()
        status["session_store"] = f"healthy ({len(sessions)} sessions)"
    except Exception as e:
        status["session_store"] = f"unhealthy: {e}"
    return {"status": "ok", "services": status}

static_dir = os.path.join(_PROJECT_ROOT, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))

from src.api.conversations import router as cr
from src.api.chat import router as chr
from src.api.tools import router as tr
from src.api.search import router as sr
app.include_router(cr, prefix="/api")
app.include_router(chr, prefix="/api")
app.include_router(tr, prefix="/api")
app.include_router(sr, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app_api:app", host="0.0.0.0", port=config.gradio_port, reload=False, log_level=config.log_level.lower())
