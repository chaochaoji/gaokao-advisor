"""Multi-session conversation storage backed by SQLite."""
import uuid
import sqlite3
from datetime import datetime


class SessionStore:
    """Manage multi-session conversations and messages in SQLite."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New Chat',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()

    def _now(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _auto_title(self, user_msg: str) -> str:
        clean = user_msg.strip()
        return clean[:20] if clean else "New Chat"

    def create_session(self) -> str:
        sid = str(uuid.uuid4())[:8]
        now = self._now()
        self.conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?,?,?,?)",
            (sid, "New Chat", now, now))
        self.conn.commit()
        return sid

    def list_sessions(self) -> list:
        rows = self.conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_messages(self, session_id: str) -> list:
        rows = self.conn.execute(
            "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def add_turn(self, session_id: str, user_msg: str, assistant_msg: str):
        now = self._now()
        self.conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?,?,?,?)",
            (session_id, "user", user_msg, now))
        self.conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?,?,?,?)",
            (session_id, "assistant", assistant_msg, now))
        count = self.conn.execute(
            "SELECT COUNT(*) FROM messages WHERE conversation_id = ?", (session_id,)
        ).fetchone()[0]
        if count <= 2:
            title = self._auto_title(user_msg)
            self.conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, session_id))
        self.conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, session_id))
        self.conn.commit()

    def rename_session(self, session_id: str, new_title: str):
        self.conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (new_title, session_id))
        self.conn.commit()

    def delete_session(self, session_id: str):
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("DELETE FROM conversations WHERE id = ?", (session_id,))
        self.conn.commit()

    def search_conversations(self, query: str) -> list:
        rows = self.conn.execute(
            "SELECT m.conversation_id, c.title, m.role, m.content, m.created_at "
            "FROM messages m JOIN conversations c ON m.conversation_id = c.id "
            "WHERE m.content LIKE ? ORDER BY m.id DESC LIMIT 50",
            (f"%{query}%",)
        ).fetchall()
        return [dict(r) for r in rows]
