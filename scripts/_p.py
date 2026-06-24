# Patch chat.py for real streaming
with open("D:/zhangxuefengagent/src/api/chat.py", "r", encoding="utf-8") as f:
    c = f.read()

# 1. Replace fake-streaming block with real streaming
old_block = """        # Stream
        for i in range(0, len(response), 30):
            yield await _sse("token", {"text": response[i:i+30]})

        session_store.add_turn(sid, msg, response)"""

new_block = """        # Stream tokens in real-time via LLM streaming API
        full_response = ""
        async for token in _stream_llm(prompt):
            full_response += token
            yield await _sse("token", {"text": token})

        session_store.add_turn(sid, msg, full_response)"""

if old_block in c:
    c = c.replace(old_block, new_block)
    print("Block 1 replaced")
else:
    print("Block 1 NOT FOUND")

with open("D:/zhangxuefengagent/src/api/chat.py", "w", encoding="utf-8") as f:
    f.write(c)
print("Done")
