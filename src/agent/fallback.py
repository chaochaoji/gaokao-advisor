from src.utils.prompt_templates import build_prompt


def handle(query, context, search_results, llm_call):
    if search_results:
        context_str = "\n".join(
            [r["content"][:300] for r in search_results[:3]]
        )
        prompt = build_prompt("general", context)
        full_prompt = f"{prompt}\n\n## 参考信息\n{context_str}\n\n## 用户消息\n{query}"
    else:
        prompt = build_prompt("general", context)
        full_prompt = f"{prompt}\n\n## 用户消息\n{query}"
    return llm_call(full_prompt)
