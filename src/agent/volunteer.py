"""Volunteer assessment handler — structured RAG with score/position data."""
from src.utils.prompt_templates import build_prompt

SCORE_DATA_HINTS = ['位次', '一分一段', '录取分', '分 |', '批次线', '分数线', '投档线', '特招线', '本科线', '分数位次']

def _is_score_data(content, source):
    """Robust score data detection: checks both hints and structural patterns."""
    combined = (content or '')[:500] + ' ' + (source or '')
    # Keyword check
    for kw in SCORE_DATA_HINTS:
        if kw in combined:
            return True
    # Structural check: lines matching "数字分 | 位次数字 | 大学名"
    import re
    if re.search(r'\d{3}\s*分\s*[|｜]\s*位次\s*\d+', combined):
        return True
    return False
POLICY_HINTS = ['招生章程', '招生工作规定', '招生计划', '录取规则']
OPINION_HINTS = ['专业介绍', '就业', '前景', '避坑', '建议', '选择']


def _classify_result(r):
    content = (r.get('content', '') or '')
    source = str(r.get('metadata', {}).get('source', '') or r.get('source', ''))
    meta = r.get('metadata', {})
    # Check metadata content_type first
    if isinstance(meta, dict) and meta.get('content_type') == 'score_data':
        return 'score'
    # Use robust score detection
    if _is_score_data(content, source):
        return 'score'
    # Fallback keyword classification
    combined = content[:300] + ' ' + source
    if isinstance(meta, dict) and meta.get('content_type') == 'score_data':
        return 'score'
    for kw in SCORE_DATA_HINTS:
        if kw in combined:
            return 'score'
    for kw in POLICY_HINTS:
        if kw in combined:
            return 'policy'
    for kw in OPINION_HINTS:
        if kw in combined:
            return 'opinion'
    return 'general'


def _format_score_block(results, user_province=""):
    if not results:
        return "（未检索到相关录取分数/位次数据）"
    lines = ["### 📊 录取分数与位次数据（来自知识库检索）", ""]
    shown = 0
    for r in results:
        content = (r.get('content', '') or '').strip()
        if not content or len(content) < 30:
            continue
        # Keep header line + first ~600 chars
        lines_list = content.split('\n')
        kept = []
        for line in lines_list:
            if len('\n'.join(kept)) < 600:
                kept.append(line)
            else:
                break
        truncated = '\n'.join(kept)
        if len(content) > len(truncated):
            truncated += "\n…"
        # Tag with province
        meta = r.get('metadata', {})
        prov = ""
        if isinstance(meta, dict):
            prov = meta.get('province', '') or user_province
        tag = f" **[{prov}数据]**" if prov else ""
        lines.append(f"---{tag}")
        lines.append(truncated)
        shown += 1
        if shown >= 6:
            break
    if not shown:
        return "（未检索到相关录取分数/位次数据）"
    lines.append("")
    lines.append("> 请优先使用标注省份的数据。若数据不含用户所在省份，可参考相近省份数据但需注明。")
    return "\n".join(lines)


def _format_knowledge_block(results, title, max_items=3):
    if not results:
        return ""
    lines = [f"### 📋 {title}", ""]
    for i, r in enumerate(results[:max_items]):
        content = (r.get('content', '') or '').strip()
        truncated = content[:400]
        if len(content) > 400:
            truncated += "…"
        lines.append(f"**参考 {i+1}:** {truncated}")
        lines.append("")
    return "\n".join(lines)


def handle(query, context, search_results, history_text, llm_call):
    # Classify results by type
    score_results = []
    policy_results = []
    opinion_results = []
    general_results = []

    for r in search_results[:15]:
        cat = _classify_result(r)
        if cat == 'score':
            score_results.append(r)
        elif cat == 'policy':
            policy_results.append(r)
        elif cat == 'opinion':
            opinion_results.append(r)
        else:
            general_results.append(r)

    blocks = []
    blocks.append(_format_score_block(score_results, context.get('province', '')))
    if policy_results:
        blocks.append(_format_knowledge_block(policy_results, "招生政策与规则", 2))
    if opinion_results:
        blocks.append(_format_knowledge_block(opinion_results, "专业与就业参考", 2))
    if general_results and not score_results:
        blocks.append(_format_knowledge_block(general_results, "其他相关信息", 3))

    structured_context = "\n\n".join(b for b in blocks if b)

    # Build user context line
    user_info = []
    for key, label in [("province", "省份"), ("score", "分数"), ("rank", "位次"),
                        ("subject_combo", "科类"), ("interests", "意向专业"),
                        ("desired_location", "期望地区")]:
        if context.get(key):
            user_info.append(f"- {label}: {context[key]}")
    # Add hint for desired location
    if context.get("desired_location"):
        user_info.append("- （优先推荐该地区院校，也可提全国更优选项）")
    else:
        user_info.append("- （期望地区未指定，基于全国范围推荐最优选择）")

    prompt = build_prompt("volunteer", context)
    parts = [prompt]

    if user_info:
        parts.append("## 当前用户信息\n" + "\n".join(user_info))
    if history_text:
        parts.append(history_text)
    parts.append(f"## 检索到的数据\n\n{structured_context}")
    parts.append(f"## 用户消息\n{query}")
    parts.append("---\n请以志愿顾问的身份对话回复。数据充足时给出具体推荐，数据不足时追问用户。保持轻松自然的聊天节奏。")

    full_prompt = "\n\n".join(parts)
    return llm_call(full_prompt)
