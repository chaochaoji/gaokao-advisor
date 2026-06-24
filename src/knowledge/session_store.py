"""Multi-session conversation storage backed by SQLite."""
import json
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
        # 新增: 结构化消息字段迁移
        for col, col_type in [("content_type", "TEXT DEFAULT 'text'"),
                               ("metadata", "TEXT")]:
            try:
                self.conn.execute(f"ALTER TABLE messages ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass  # 列已存在
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
            "SELECT role, content, content_type, metadata, created_at "
            "FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        result = []
        for r in rows:
            msg = dict(r)
            # content_type 为空时默认为 'text'
            if not msg.get('content_type'):
                msg['content_type'] = 'text'
            # metadata 为 JSON 字符串时解析
            if msg.get('metadata') and isinstance(msg['metadata'], str):
                try:
                    msg['metadata'] = json.loads(msg['metadata'])
                except json.JSONDecodeError:
                    pass
            result.append(msg)
        return result

    def add_turn(self, session_id: str, user_msg: str, assistant_msg,
                 content_type: str = 'text', metadata: str = None):
        """Add a user-assistant turn. assistant_msg can be str or dict.
        If dict, it's stored as JSON in content and content_type='volunteer_assessment'.
        """
        # 兼容旧的 dict 传入方式
        if isinstance(assistant_msg, dict):
            metadata = json.dumps(assistant_msg.get('structured_data', {}),
                                  ensure_ascii=False)
            content_type = assistant_msg.get('content_type', 'volunteer_assessment')
            assistant_msg = assistant_msg.get('fallback_text', '')

        now = self._now()
        self.conn.execute(
            "INSERT INTO messages (conversation_id, role, content, content_type, metadata, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (session_id, "user", user_msg, "text", None, now))
        self.conn.execute(
            "INSERT INTO messages (conversation_id, role, content, content_type, metadata, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (session_id, "assistant", assistant_msg, content_type, metadata, now))
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

    def session_exists(self, session_id: str) -> bool:
        """Quick check if a session exists (O(1) query)."""
        if not session_id or session_id == "new":
            return False
        row = self.conn.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (session_id,)
        ).fetchone()
        return row is not None

    def get_history(self, session_id: str, max_turns: int = 6) -> list:
        """Get most recent conversation turns for context injection."""
        rows = self.conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, max_turns * 2)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def get_context(self, session_id: str) -> dict:
        """Extract previously stated user context (province/score/subject) from history."""
        import re
        rows = self.conn.execute(
            "SELECT content FROM messages WHERE conversation_id = ? AND role = 'user' ORDER BY id DESC LIMIT 10",
            (session_id,)
        ).fetchall()
        ctx = {}
        for (content,) in reversed(rows):
            if not ctx.get("province"):
                m = re.search(r'(河南|河北|山东|广东|江苏|四川|湖北|湖南|浙江|安徽|福建|江西|辽宁|陕西|山西|云南|贵州|广西|甘肃|吉林|黑龙江|内蒙古|新疆|海南|宁夏|青海|西藏|北京|上海|天津|重庆)', content)
                if m:
                    ctx["province"] = m.group(1)
            if not ctx.get("score"):
                m = re.search(r'(\d{3})\s*分', content)
                if m:
                    ctx["score"] = int(m.group(1))
            if not ctx.get("subject_combo"):
                if "物理" in content or "理科" in content:
                    ctx["subject_combo"] = "物理类"
                elif "历史" in content or "文科" in content:
                    ctx["subject_combo"] = "历史类"
        return ctx

    def search_conversations(self, query: str) -> list:
        rows = self.conn.execute(
            "SELECT m.conversation_id, c.title, m.role, m.content, m.created_at "
            "FROM messages m JOIN conversations c ON m.conversation_id = c.id "
            "WHERE m.content LIKE ? ORDER BY m.id DESC LIMIT 50",
            (f"%{query}%",)
        ).fetchall()
        return [dict(r) for r in rows]
