"""Tests for SessionStore."""
import sqlite3
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from knowledge.session_store import SessionStore


@pytest.fixture
def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return SessionStore(conn)


def test_create_session_returns_string(store):
    sid = store.create_session()
    assert isinstance(sid, str) and len(sid) == 8


def test_list_sessions_empty(store):
    assert store.list_sessions() == []


def test_list_sessions_after_create(store):
    store.create_session()
    assert len(store.list_sessions()) == 1
    assert store.list_sessions()[0]["title"] == "New Chat"


def test_add_turn_and_get_messages(store):
    sid = store.create_session()
    store.add_turn(sid, "Hello", "Hi there")
    msgs = store.get_messages(sid)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user" and msgs[1]["role"] == "assistant"


def test_auto_title_on_first_message(store):
    sid = store.create_session()
    store.add_turn(sid, "Hello World from user", "Hi")
    assert store.list_sessions()[0]["title"] == "Hello World from use"


def test_delete_session(store):
    sid = store.create_session()
    store.add_turn(sid, "msg", "resp")
    store.delete_session(sid)
    assert store.list_sessions() == []
    assert store.get_messages(sid) == []


def test_rename_session(store):
    sid = store.create_session()
    store.rename_session(sid, "Custom Title")
    assert store.list_sessions()[0]["title"] == "Custom Title"


def test_search_conversations(store):
    sid = store.create_session()
    store.add_turn(sid, "Python programming tips", "Here you go")
    assert len(store.search_conversations("Python")) >= 1
