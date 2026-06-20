from src.utils.prompt_templates import build_prompt


def handle(query, context, search_results, llm_call):
    prompt = build_prompt("style_chat", context)
    full_prompt = f"{prompt}\n\n## 用户消息\n{query}"
    return llm_call(full_prompt)
