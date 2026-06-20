# tests/test_router.py
import json
from src.agent.router import classify_intent, ROUTER_PROMPT


def fake_llm(response_json):
    def call(prompt, msg, **kw):
        return json.dumps(response_json)
    return call


def test_classify_volunteer():
    result = classify_intent(
        fake_llm({"scene": "volunteer", "confidence": 0.95}),
        "河南理科580分计算机推荐什么学校"
    )
    assert result["scene"] == "volunteer"


def test_classify_opinion():
    result = classify_intent(
        fake_llm({"scene": "opinion", "confidence": 0.8}),
        "土木工程还值得学吗"
    )
    assert result["scene"] == "opinion"


def test_classify_style_chat():
    result = classify_intent(
        fake_llm({"scene": "style_chat", "confidence": 0.85}),
        "张老师我觉得自己考不上好迷茫"
    )
    assert result["scene"] == "style_chat"


def test_classify_general():
    result = classify_intent(
        fake_llm({"scene": "general", "confidence": 0.95}),
        "今天天气怎么样"
    )
    assert result["scene"] == "general"


def test_classify_fallback_on_error():
    result = classify_intent(
        fake_llm("invalid json!!!"),
        "你好"
    )
    assert result["scene"] == "general"
    assert result["confidence"] < 0.5


def test_classify_missing_scene():
    result = classify_intent(
        fake_llm({"confidence": 0.7}),
        "随便聊聊"
    )
    assert result["scene"] == "general"


def test_classify_unknown_scene():
    result = classify_intent(
        fake_llm({"scene": "unknown_scene", "confidence": 0.9}),
        "测试"
    )
    assert result["scene"] == "general"
