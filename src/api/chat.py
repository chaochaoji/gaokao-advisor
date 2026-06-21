"""Chat SSE streaming endpoint."""
import json, time
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from src.api.dependencies import session_store, hybrid_search, safety, config, logger
from src.agent.router import classify_intent
from src.agent.volunteer import handle as vol_h
from src.agent.opinion import handle as op_h
from src.agent.style_chat import handle as sc_h
from src.agent.fallback import handle as fb_h
from src.utils.conversation import SessionContext

router = APIRouter(tags=["chat"])

HANDLERS = {"volunteer":vol_h, "opinion":op_h, "style_chat":sc_h, "general":fb_h}
REJECT = {"jailbreak":"[安全提醒] 你的消息包含不被允许的指令。", "privacy":"[安全提醒] 请勿查询他人隐私信息。", "abuse":"[安全提醒] 请使用文明用语交流。", "regional_attack":"[安全提醒] 地域攻击言论不被允许。"}

async def _sse(event, data):
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}

@router.get("/chat/stream")
async def chat_stream(msg: str, session: str = "new", mode: str = "agent"):
    t0 = time.time()
    if not msg or not msg.strip():
        async def g():
            yield await _sse("done", {"error": "empty"})
        return EventSourceResponse(g())

    async def gen():
        # Safety
        check = safety.check(msg)
        if not check["safe"]:
            rm = REJECT.get(check["category"], "[安全提醒] 消息包含不适当内容。")
            yield await _sse("thinking", {"text": f"Safety: {check['category']}"})
            yield await _sse("token", {"text": rm})
            yield await _sse("done", {"thinking_time": round(time.time()-t0,2)})
            return

        # Validate or create session
        sid = session
        if not sid or sid == "new" or not any(s["id"] == sid for s in session_store.list_sessions()):
            sid = session_store.create_session()
        ctx = SessionContext()

        # Intent routing
        intent = classify_intent(lambda sp,um: _call_llm(sp,um), msg)
        scene = intent.get("scene", "general")
        yield await _sse("thinking", {"text": f"Intent: {scene} (confidence: {intent.get('confidence',0):.2f})"})

        # Search
        results = hybrid_search.search(msg, scene, ctx.get_context()["context_state"])
        sources = [r.get("content","")[:80] for r in results[:3]] if results else []
        yield await _sse("thinking", {"text": f"Found {len(results)} results", "sources": sources})

        # Handler
        handler = HANDLERS.get(scene, fb_h)
        response = handler(msg, ctx.get_context()["context_state"], results, lambda p,um=None: _call_llm(p,um))

        # Stream
        for i in range(0, len(response), 30):
            yield await _sse("token", {"text": response[i:i+30]})

        session_store.add_turn(sid, msg, response)
        ctx.update(msg)
        yield await _sse("done", {"session_id": sid, "scene": scene, "thinking_time": round(time.time()-t0,2)})

    return EventSourceResponse(gen())


def _call_llm(sp, um=None):
    import anthropic
    from openai import OpenAI
    client = None; model = ""
    if config.llm_primary_api_key:
        try:
            client = anthropic.Anthropic(api_key=config.llm_primary_api_key, base_url=config.llm_primary_base_url or None, timeout=config.llm_timeout)
            model = config.llm_primary_model
        except Exception: pass
    if client is None and config.llm_fallback_api_key:
        try:
            client = OpenAI(api_key=config.llm_fallback_api_key, base_url=config.llm_fallback_base_url, timeout=config.llm_timeout)
            model = config.llm_fallback_model
        except Exception: pass
    if client is None: return "[系统提示] LLM 未配置。"
    if um is None: um = sp; sp = None
    try:
        if hasattr(client, "messages"):
            kw = {}; 
            if sp: kw["system"] = sp
            resp = client.messages.create(model=model, max_tokens=2048, messages=[{"role":"user","content":um}], **kw)
            return resp.content[0].text
        else:
            msgs = []
            if sp: msgs.append({"role":"system","content":sp})
            msgs.append({"role":"user","content":um})
            resp = client.chat.completions.create(model=model, messages=msgs, max_tokens=2048, temperature=0.7)
            return resp.choices[0].message.content
    except Exception as e:
        logger.log_error("llm", "call_failed", e)
        return "[系统提示] LLM 调用失败。"
