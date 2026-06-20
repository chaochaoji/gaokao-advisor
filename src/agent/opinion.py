from src.utils.prompt_templates import build_prompt


def handle(query, context, search_results, llm_call):
    context_str = "\n".join(
        [f"[来源: {r.get('metadata',{}).get('source','?')} {r.get('metadata',{}).get('date','?')}]\n{r['content']}"
         for i, r in enumerate(search_results[:5])]
    )
    prompt = build_prompt("opinion", context)
    full_prompt = f"{prompt}\n\n## 相关语料\n{context_str}\n\n## 用户问题\n{query}"
    return llm_call(full_prompt)
