import json
import logging

logger = logging.getLogger("zhangxuefeng")

ROUTER_PROMPT = """判断用户意图，仅输出 JSON:
{"scene":"volunteer|opinion|style_chat|general","confidence":0.0-1.0}

场景说明:
- volunteer: 高考志愿、分数、选专业、选学校、考研择校
- opinion: 询问张雪峰对某个专业/行业/现象的看法
- style_chat: 闲聊、心态、人生建议（不带具体志愿参数）
- general: 以上都不是或不好判断

示例:
"河南理科580分计算机推荐" -> {"scene":"volunteer","confidence":0.95}
"土木工程还值得学吗" -> {"scene":"opinion","confidence":0.7}
"张老师我觉得自己考不上好迷茫" -> {"scene":"style_chat","confidence":0.85}
"今天天气怎么样" -> {"scene":"general","confidence":0.95}
"""


def classify_intent(llm_call, user_msg):
    try:
        response = llm_call(ROUTER_PROMPT, user_msg)
        result = json.loads(response.strip())
        if "scene" in result and result["scene"] in (
            "volunteer", "opinion", "style_chat", "general"
        ):
            return {"scene": result["scene"], "confidence": result.get("confidence", 0.5)}
    except Exception as e:
        logger.warning(f"Router classification failed: {e}, fallback to general")
    return {"scene": "general", "confidence": 0.3}
