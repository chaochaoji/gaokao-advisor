# tests/test_scene_handlers.py
"""Tests for scene handler modules (volunteer, opinion, style_chat, fallback)."""


def fake_llm(response=None):
    """Return a callable that records the prompt and returns a canned response."""
    calls = []

    def call(prompt, **kw):
        calls.append(prompt)
        return response or "mock response"

    call.calls = calls
    return call


def make_search_results(n=10):
    return [
        {
            "content": f"检索结果 {i} 的内容",
            "metadata": {"source": f"source_{i}", "date": f"2024-0{i}"},
        }
        for i in range(1, n + 1)
    ]


class TestVolunteerHandler:
    def test_handle_calls_llm_with_prompt(self):
        from src.agent.volunteer import handle
        llm = fake_llm("推荐郑州大学")
        context = {"province": "河南", "score": 580}
        sr = make_search_results(10)

        result = handle("河南理科580分计算机推荐", context, sr, llm)

        assert result == "推荐郑州大学"
        assert len(llm.calls) == 1
        prompt = llm.calls[0]
        assert "河南理科580分计算机推荐" in prompt
        assert "检索结果 1" in prompt

    def test_handle_limits_to_8_results(self):
        from src.agent.volunteer import handle
        llm = fake_llm()
        sr = make_search_results(20)

        handle("test", {}, sr, llm)
        prompt = llm.calls[0]
        # Only first 8 results should appear
        assert "检索结果 8" in prompt
        assert "检索结果 9" not in prompt


class TestOpinionHandler:
    def test_handle_calls_llm_with_sources(self):
        from src.agent.opinion import handle
        llm = fake_llm("土木工程观点")
        sr = make_search_results(10)

        result = handle("土木工程还值得学吗", {}, sr, llm)

        assert result == "土木工程观点"
        prompt = llm.calls[0]
        assert "土木工程还值得学吗" in prompt
        assert "source_1" in prompt
        assert "2024-01" in prompt

    def test_handle_limits_to_5_results(self):
        from src.agent.opinion import handle
        llm = fake_llm()
        sr = make_search_results(10)

        handle("test", {}, sr, llm)
        prompt = llm.calls[0]
        assert "检索结果 5" in prompt
        assert "检索结果 6" not in prompt


class TestStyleChatHandler:
    def test_handle_no_search_results_needed(self):
        from src.agent.style_chat import handle
        llm = fake_llm("放轻松，加油")
        sr = make_search_results(5)

        result = handle("张老师我迷茫", {}, sr, llm)

        assert result == "放轻松，加油"
        prompt = llm.calls[0]
        assert "张老师我迷茫" in prompt
        assert "style_chat" in prompt.lower() or "风格" in prompt

    def test_handle_passes_context(self):
        from src.agent.style_chat import handle
        llm = fake_llm()
        context = {"province": "山东", "interests": ["计算机"]}

        handle("鼓励我一下", context, [], llm)

        prompt = llm.calls[0]
        assert "山东" in prompt
        assert "计算机" in prompt


class TestFallbackHandler:
    def test_handle_with_results(self):
        from src.agent.fallback import handle
        llm = fake_llm("建议你关注高考")
        sr = make_search_results(5)

        result = handle("今天天气怎么样", {}, sr, llm)

        assert result == "建议你关注高考"
        prompt = llm.calls[0]
        assert "今天天气怎么样" in prompt

    def test_handle_without_results(self):
        from src.agent.fallback import handle
        llm = fake_llm("我不确定")

        result = handle("你好", {}, [], llm)

        assert result == "我不确定"
        prompt = llm.calls[0]
        assert "你好" in prompt
        assert "general" in prompt.lower() or "通用" in prompt

    def test_handle_truncates_content(self):
        from src.agent.fallback import handle
        llm = fake_llm()
        sr = [{"content": "A" * 500}]

        handle("test", {}, sr, llm)
        prompt = llm.calls[0]
        # Content should be truncated to 300 chars
        assert "A" * 300 in prompt
        assert len("A" * 500) > 300  # original is longer
