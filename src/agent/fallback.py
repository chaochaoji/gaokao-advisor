from src.utils.prompt_templates import build_prompt


def handle(query, context, search_results, history_text, llm_call):
    prompt = build_prompt("general", context)
    parts = [prompt]

    if context:
        parts.append("## 用户信息\n" + "\n".join(f"- {k}: {v}" for k, v in context.items()))
    if history_text:
        parts.append(history_text)

    if search_results:
        snippets = []
        for r in search_results[:3]:
            content = (r.get("content") or "")[:300]
            if content:
                # Try to truncate at sentence boundary
                for sep in ["\n\n", "。", "；", "\n"]:
                    idx = content.rfind(sep, 0, 300)
                    if idx > 100:
                        content = content[:idx+1]
                        break
                snippets.append(content)
        if snippets:
            context_str = "\n".join(snippets)
            parts.append(f"## 参考信息\n{context_str}\n\n（未检索到相关数据时的标注：以下回答基于通用知识，非来自知识库。）")

    if not search_results:
        parts.append("（未检索到相关信息，请基于通用知识回答，并明确告知用户这是通用建议而非基于专属数据。）")

    parts.append(f"## 用户消息\n{query}")
    full_prompt = "\n\n".join(parts)
    return llm_call(full_prompt)
