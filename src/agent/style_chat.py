from src.utils.prompt_templates import build_prompt


def handle(query, context, search_results, history_text, llm_call):
    prompt = build_prompt("style_chat", context)

    # Attach light search results if available (for reference, not primary)
    context_str = ""
    if search_results:
        snippets = [r.get("content", "")[:200] for r in search_results[:3] if r.get("content")]
        if snippets:
            context_str = "\n## 参考信息（可选参考，不强依赖）\n" + "\n---\n".join(snippets)

    user_info = ""
    if context:
        user_info = "\n## 用户信息\n" + "\n".join(f"- {k}: {v}" for k, v in context.items())

    history = ""
    if history_text:
        history = "\n" + history_text

    full_prompt = f"{prompt}{user_info}{history}\n{context_str}\n\n## 用户消息\n{query}"
    return llm_call(full_prompt)
