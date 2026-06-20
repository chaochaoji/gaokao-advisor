import json
import os

import pytest

from src.utils.logger import AgentLogger
from src.utils.health import HealthManager


@pytest.fixture
def logger(temp_dir):
    l = AgentLogger(log_dir=temp_dir, session_id="test")
    yield l
    l.close()


class TestAgentLogger:
    def test_log_error_updates_health(self, logger, temp_dir):
        try:
            raise ConnectionError("ChromaDB down")
        except Exception as e:
            logger.log_error(
                component="chromadb",
                event="search_failed",
                error=e,
                fallback_action="skip_vector",
                user_query="test",
            )
        health = json.load(open(os.path.join(temp_dir, "health.json")))
        assert health["services"]["chromadb"]["status"] == "unhealthy"

    def test_log_warning_sets_degraded(self, logger, temp_dir):
        logger.log_warning(
            component="reranker",
            event="timeout",
            fallback_action="use_original",
        )
        health = json.load(open(os.path.join(temp_dir, "health.json")))
        assert health["services"]["reranker"]["status"] == "degraded"

    def test_health_report_includes_components(self, logger, temp_dir):
        try:
            raise TimeoutError("LLM timeout")
        except Exception as e:
            logger.log_error(
                component="llm_primary",
                event="timeout",
                error=e,
                fallback_action="switch_fallback",
                user_query="test",
            )
        report = HealthManager.get_report(temp_dir)
        assert "llm_primary" in report
