# tests/test_conversation.py
from src.utils.conversation import SessionContext


def test_context_state_persistence():
    sc = SessionContext()
    sc.update("我是河南的理科生")
    assert sc.context_state["province"] == "河南"


def test_score_update():
    sc = SessionContext()
    sc.update("我考了580分")
    assert sc.context_state["score"] == 580


def test_category_extraction_physics():
    sc = SessionContext()
    sc.update("我是理科生")
    assert sc.context_state["category"] == "物理类"


def test_category_extraction_history():
    sc = SessionContext()
    sc.update("我是历史类考生")
    assert sc.context_state["category"] == "历史类"


def test_multiple_state_extraction():
    sc = SessionContext()
    sc.update("我是河南的理科生，考了620分")
    assert sc.context_state["province"] == "河南"
    assert sc.context_state["score"] == 620
    assert sc.context_state["category"] == "物理类"


def test_no_state_change_on_irrelevant():
    sc = SessionContext()
    sc.update("今天天气真好")
    assert sc.context_state["province"] is None
    assert sc.context_state["score"] is None


def test_get_context_includes_state():
    sc = SessionContext()
    sc.update("我是广东的文科生")
    ctx = sc.get_context()
    assert "context_state" in ctx
    assert ctx["context_state"]["province"] == "广东"


def test_state_accumulates_across_updates():
    sc = SessionContext()
    sc.update("我是四川的")
    sc.update("考了590分")
    assert sc.context_state["province"] == "四川"
    assert sc.context_state["score"] == 590


def test_resolve_references_substitutes_short():
    sc = SessionContext()
    sc.context_state["last_schools"] = ["郑州大学", "河南大学"]
    result = sc.resolve_references("你觉得郑州怎么样")
    assert "郑州大学" in result


def test_resolve_references_no_match():
    sc = SessionContext()
    sc.context_state["last_schools"] = ["郑州大学"]
    result = sc.resolve_references("清华怎么样")
    assert result == "清华怎么样"
