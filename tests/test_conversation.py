# tests/test_conversation.py
from src.utils.conversation import ConversationManager


def test_context_state_persistence():
    cm = ConversationManager()
    cm.add_turn("我是河南的理科生", "你好河南的考生...")
    assert cm.context_state["province"] == "河南"


def test_score_update():
    cm = ConversationManager()
    cm.add_turn("我考了580分", "580分...")
    assert cm.context_state["score"] == 580


def test_window_limit():
    cm = ConversationManager(max_window=2)
    for i in range(5):
        cm.add_turn(f"问题{i}", f"回答{i}")
    recent = cm.get_recent_messages(3)
    assert len(recent) == 6


def test_category_extraction_physics():
    cm = ConversationManager()
    cm.add_turn("我是理科生", "好的")
    assert cm.context_state["category"] == "物理类"


def test_category_extraction_history():
    cm = ConversationManager()
    cm.add_turn("我是历史类考生", "好的")
    assert cm.context_state["category"] == "历史类"


def test_multiple_state_extraction():
    cm = ConversationManager()
    cm.add_turn("我是河南的理科生，考了620分", "好的")
    assert cm.context_state["province"] == "河南"
    assert cm.context_state["score"] == 620
    assert cm.context_state["category"] == "物理类"


def test_no_state_change_on_irrelevant():
    cm = ConversationManager()
    cm.add_turn("今天天气真好", "是啊")
    assert cm.context_state["province"] is None
    assert cm.context_state["score"] is None


def test_get_context_includes_recent():
    cm = ConversationManager(max_window=3)
    cm.add_turn("问题1", "回答1")
    cm.add_turn("问题2", "回答2")
    ctx = cm.get_context()
    assert "context_state" in ctx
    assert "recent_messages" in ctx
    assert len(ctx["recent_messages"]) == 4  # 2 turns = 4 messages


def test_get_recent_messages_default_window():
    cm = ConversationManager(max_window=3)
    for i in range(10):
        cm.add_turn(f"问题{i}", f"回答{i}")
    recent = cm.get_recent_messages()  # default: use max_window
    assert len(recent) == 6  # 3 turns * 2


def test_resolve_references_substitutes_short():
    cm = ConversationManager()
    cm.context_state["last_schools"] = ["郑州大学", "河南大学"]
    result = cm.resolve_references("你觉得郑州怎么样")
    assert "郑州大学" in result


def test_resolve_references_no_match():
    cm = ConversationManager()
    cm.context_state["last_schools"] = ["郑州大学"]
    result = cm.resolve_references("清华怎么样")
    assert result == "清华怎么样"
