N=chr(10)
Q=chr(34)
S=chr(39)
out=[]
out.append('"""LLM client with streaming."""')
out.append('from src.api.dependencies import config,logger')
with open("D:/zhangxuefengagent/src/api/llm_client.py","w",encoding="utf-8") as f:
    f.write(N.join(out))
print("ok")
