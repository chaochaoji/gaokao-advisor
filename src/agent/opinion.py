from src.utils.prompt_templates import build_prompt


def handle(query, context, search_results, history_text, llm_call):
    if search_results:
        context_str = "\n".join(
            [f"[来源: {r.get('metadata',{}).get('source','?')} {r.get('metadata',{}).get('date','?')}]\n{r.get('content','')}"
             for r in search_results[:5] if r.get('content')]
        )
        prompt = build_prompt("opinion", context)
        parts = [prompt]
        if context:
            parts.append(f"## 用户上下文\n" + "\n".join(f"{k}: {v}" for k, v in context.items()))
        if history_text:
            parts.append(history_text)
        parts.append(f"## 相关语料\n{context_str}")
        parts.append(f"## 用户问题\n{query}")
        full_prompt = "\n\n".join(parts)
    else:
        prompt = build_prompt("general", context)
        full_prompt = f"{prompt}\n\n（未检索到相关语料，请基于通用知识回答并注明）\n\n## 用户问题\n{query}"
    return llm_call(full_prompt)
