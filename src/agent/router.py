"""Intent classifier — fast regex pre-check + LLM fallback."""
import json, re, logging

logger = logging.getLogger("gaokao_ai")

ROUTER_PROMPT = """判断用户意图，仅输出如下 JSON (不要用代码围栏包裹):
{"scene":"volunteer|opinion|style_chat|general","confidence":0.0-1.0}

场景说明:
- volunteer: 高考志愿、分数、选专业、选学校、考研择校
- opinion: 询问对某个专业/行业/现象怎么看、值不值得
- style_chat: 闲聊、心态、人生建议（不带具体志愿参数）
- general: 以上都不是

示例:
"河南理科580分计算机推荐" -> {"scene":"volunteer","confidence":0.95}
"土木工程还值得学吗" -> {"scene":"opinion","confidence":0.7}
"我觉得自己考不上好迷茫" -> {"scene":"style_chat","confidence":0.85}
"今天天气怎么样" -> {"scene":"general","confidence":0.95}
"""


def _extract_json(text: str) -> str:
    """Extract JSON from text that may include code fences or extra text."""
    # Try code fence first
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        return m.group(1)
    # Try bare JSON object
    m = re.search(r'\{[^{}]*"scene"[^{}]*\}', text)
    if m:
        return m.group(0)
    return text.strip()


def classify_intent(llm_call, user_msg):
    try:
        response = llm_call(ROUTER_PROMPT, user_msg)
        json_str = _extract_json(response)
        result = json.loads(json_str)
        scene = str(result.get("scene", "general")).lower()
        confidence = float(result.get("confidence", 0.5))

        valid_scenes = {"volunteer", "opinion", "style_chat", "general"}
        if scene not in valid_scenes:
            scene = "general"
            confidence = 0.3

        return {"scene": scene, "confidence": confidence}
    except Exception as e:
        logger.warning(f"Router classification failed: {e}, fallback to general")
    return {"scene": "general", "confidence": 0.3}
