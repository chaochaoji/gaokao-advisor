"""Session CRUD API."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.api.dependencies import session_store

router = APIRouter(tags=["conversations"])

class RenameBody(BaseModel):
    title: str

@router.post("/conversations")
def create_session():
    sid = session_store.create_session()
    return {"id": sid, "title": "New Chat"}

@router.get("/conversations")
def list_sessions():
    return session_store.list_sessions()

@router.get("/conversations/{sid}/messages")
def get_messages(sid: str):
    msgs = session_store.get_messages(sid)
    if not msgs and not any(s["id"]==sid for s in session_store.list_sessions()):
        raise HTTPException(status_code=404, detail="Session not found")
    return msgs

@router.delete("/conversations/{sid}")
def delete_session(sid: str):
    session_store.delete_session(sid)
    return {"ok": True}

@router.patch("/conversations/{sid}/title")
def rename_session(sid: str, body: RenameBody):
    session_store.rename_session(sid, body.title)
    return {"ok": True}
