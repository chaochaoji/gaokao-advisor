N = chr(10)
Q = chr(34)
S = chr(39)

with open("D:/zhangxuefengagent/src/api/chat.py", "r", encoding="utf-8") as f:
    c = f.read()

# 1. Replace handler + streaming block with prompt building + streaming
old = """        # Handler
        handler = HANDLERS.get(scene, fb_h)
        response = handler(msg, ctx.get_context()["context_state"], results, lambda p,um=None: _call_llm(p,um))

        # Stream tokens in real-time via LLM streaming API
        full_response = ""
        async for token in _stream_llm(prompt):
            full_response += token
            yield await _sse("token", {"text": token})"""

new = """        # Build prompt and stream LLM tokens in real-time
        prompt = build_prompt(scene, ctx.get_context()["context_state"])
        nl = chr(10)
        ctx_str = nl.join([f"[{i+1}] {r['content']}" for i, r in enumerate(results[:8])])
        prompt = f"{prompt}{nl}{nl}## 检索信息{nl}{ctx_str}{nl}{nl}## 用户消息{nl}{msg}"

        full_response = ""
        async for token in _stream_llm(prompt):
            full_response += token
            yield await _sse("token", {"text": token})"""

if old in c:
    c = c.replace(old, new)
    print("Handler block replaced")
else:
    print("Handler block NOT FOUND - checking exact content...")
    for i, line in enumerate(c.split(N)):
        if "Handler" in line:
            print(f"  L{i}: {repr(line)}")

with open("D:/zhangxuefengagent/src/api/chat.py", "w", encoding="utf-8") as f:
    f.write(c)
print("Part 1 done")
