import json
import logging
import traceback
import os
from datetime import datetime
from pathlib import Path


class AgentLogger:
    SUGGESTIONS = {
        "chromadb": {
            "ConnectionError": "ChromaDB 不可达。检查 docker compose up -d",
        },
        "sqlite": {
            "OperationalError": "SQLite 数据库文件可能被锁定",
        },
        "llm_primary": {
            "ConnectionError": "LLM API 不可达，检查 API key",
            "Timeout": "LLM 响应超时，已切备用模型",
        },
        "reranker": {
            "ConnectionError": "Reranker 不可用，检查 API 配置",
        },
    }

    def __init__(self, log_dir="logs", session_id=""):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id

        self.logger = logging.getLogger("zhangxuefeng")
        self.logger.setLevel(logging.DEBUG)

        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        )
        for fname, level in [("app.log", logging.DEBUG), ("error.log", logging.ERROR)]:
            h = logging.FileHandler(self.log_dir / fname, encoding="utf-8")
            h.setLevel(level)
            h.setFormatter(fmt)
            self.logger.addHandler(h)

    def _update_health(self, component, status, detail):
        hp = self.log_dir / "health.json"
        health = {"updated_at": datetime.now().isoformat(), "services": {}, "recent_errors": []}
        if hp.exists():
            try:
                health = json.loads(hp.read_text(encoding="utf-8"))
            except Exception:
                pass

        health["services"][component] = {
            "status": status,
            "last_error": str(detail.get("error", ""))[:500] if status != "healthy" else None,
            "last_checked": datetime.now().isoformat(),
        }

        if status == "unhealthy":
            health.setdefault("recent_errors", [])
            health["recent_errors"].insert(0, {
                "time": datetime.now().isoformat(),
                "component": component,
                "error": str(detail.get("error", ""))[:200],
                "action_taken": detail.get("fallback_action", ""),
                "fix_suggestion": detail.get("fix_suggestion", ""),
            })
            health["recent_errors"] = health["recent_errors"][:20]

        hp.write_text(json.dumps(health, ensure_ascii=False, indent=2))

    def log_error(self, component, event, error, fallback_action="",
                  user_query="", detail=None):
        error_type = type(error).__name__
        suggestion = self.SUGGESTIONS.get(component, {}).get(error_type, "")
        entry = {
            "timestamp": datetime.now().isoformat(), "level": "ERROR",
            "component": component, "event": event,
            "detail": {
                "error": str(error), "error_type": error_type,
                "traceback": traceback.format_exc(),
                "fallback_action": fallback_action,
                "fix_suggestion": suggestion,
                "user_query": user_query,
                **(detail or {})
            }
        }
        self.logger.error(json.dumps(entry, ensure_ascii=False))
        self._update_health(component, "unhealthy", entry["detail"])

    def log_warning(self, component, event, fallback_action="", detail=None):
        self.logger.warning(json.dumps({
            "timestamp": datetime.now().isoformat(), "level": "WARNING",
            "component": component, "event": event,
            "fallback_action": fallback_action, "detail": detail or {}
        }, ensure_ascii=False))
        self._update_health(component, "degraded", detail or {})

    def log_info(self, component, event, detail=None):
        self.logger.info(json.dumps({
            "timestamp": datetime.now().isoformat(), "level": "INFO",
            "component": component, "event": event,
            "detail": detail or {}
        }, ensure_ascii=False))

    def close(self):
        """Close and remove all logging handlers, releasing file handles."""
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)
