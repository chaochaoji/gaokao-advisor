N = chr(10)
Q = chr(34)
S = chr(39)
with open("D:/zhangxuefengagent/src/api/chat.py","r",encoding="utf-8") as f:
    c = f.read()
idx = c.find("def _call_llm(")
print("_call_llm at:", idx)
prefix = c[:idx]
print("Prefix length:", len(prefix))
