with open("D:/zhangxuefengagent/src/api/llm_client.py", "w", encoding="utf-8") as f:
    N = chr(10)
    lines = []
    lines.append("# LLM client with streaming")
    lines.append("from src.api.dependencies import config, logger")
    f.write(N.join(lines))
print("ok")
