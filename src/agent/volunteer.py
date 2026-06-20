from src.utils.prompt_templates import build_prompt


def handle(query, context, search_results, llm_call):
    context_str = "\n".join(
        [f"[检索结果 {i+1}] {r['content']}" for i, r in enumerate(search_results[:8])]
    )
    prompt = build_prompt("volunteer", context)
    full_prompt = f"{prompt}\n\n## 检索到的相关信息\n{context_str}\n\n## 用户问题\n{query}"
    return llm_call(full_prompt)
