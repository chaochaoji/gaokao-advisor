"""Conversation search API."""
from fastapi import APIRouter, Query
from src.api.dependencies import session_store

router = APIRouter(tags=["search"])

@router.get("/tools/search")
def search_conversations(q: str = Query(..., min_length=1)):
    results = session_store.search_conversations(q)
    return {"query": q, "results": results, "count": len(results)}
