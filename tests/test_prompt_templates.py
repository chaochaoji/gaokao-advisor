# tests/test_prompt_templates.py
from src.utils.prompt_templates import (
    MAIN_SYSTEM_PROMPT, SCENE_PROMPTS, build_prompt
)


def test_main_prompt_contains_five_steps():
    assert "分数定位" in MAIN_SYSTEM_PROMPT
    assert "专业筛选" in MAIN_SYSTEM_PROMPT
    assert "地域匹配" in MAIN_SYSTEM_PROMPT
    assert "院校定档" in MAIN_SYSTEM_PROMPT
    assert "风险对冲" in MAIN_SYSTEM_PROMPT

def test_scene_prompts_have_all_four_scenes():
    for scene in ["volunteer", "opinion", "style_chat", "general"]:
        assert scene in SCENE_PROMPTS

def test_build_prompt_includes_scene():
    result = build_prompt("volunteer", {"user_query": "test"})
    assert "volunteer" in result.lower() or "志愿建议" in result

def test_build_prompt_includes_user_context():
    result = build_prompt("volunteer", {
        "user_query": "河南理科580分计算机",
        "province": "河南",
        "score": 580
    })
    assert "河南" in result
    assert "580" in result
