with open("D:/zhangxuefengagent/src/api/chat.py", "r", encoding="utf-8") as f:
    c = f.read()

# Replace handler block
old = "        # Handler"
idx = c.find(old)
print("Handler at:", idx)

# Replace streaming block  
old2 = "        # Stream tokens in real-time via LLM streaming API"
idx2 = c.find(old2)
print("Stream at:", idx2)

# Show the handler section
lines = c.split(chr(10))
for i in range(max(0,idx//100-2), min(len(lines), idx//100+80)):
    l = lines[i]
    if any(k in l for k in ["Handler", "handler", "prompt", "Stream", "stream", "full_response"]):
        print(f"  L{i}: {l}")
