"""Chat SSE streaming endpoint."""
import json, time, re
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

MAX_HISTORY_TURNS = 6  # Keep last 6 turns as conversation context
INTENT_CONFIDENCE_THRESHOLD = 0.5  # Route to general if below this


def _extract_context(msg, session_id):
    """Extract province/score/subject from message text and session history."""
    ctx = {"province": None, "score": None, "rank": None, "subject_combo": None, "interests": []}

    # Try to extract from current message first
    province_map = {
        "北京": "北京","天津": "天津","上海": "上海","重庆": "重庆",
        "河北": "河北","山西": "山西","辽宁": "辽宁","吉林": "吉林",
        "黑龙江": "黑龙江","江苏": "江苏","浙江": "浙江","安徽": "安徽",
        "福建": "福建","江西": "江西","山东": "山东","河南": "河南",
        "湖北": "湖北","湖南": "湖南","广东": "广东","海南": "海南",
        "四川": "四川","贵州": "贵州","云南": "云南","陕西": "陕西",
        "甘肃": "甘肃","青海": "青海","台湾": "台湾",
        "内蒙古": "内蒙古","广西": "广西","西藏": "西藏",
        "宁夏": "宁夏","新疆": "新疆",
    }
    for name, abbr in province_map.items():
        if name in msg or abbr + "省" in msg or abbr + "市" in msg:
            ctx["province"] = name
            break

    # Extract score (3-digit number followed by 分)
    score_match = re.search(r'(\d{3})\s*分', msg)
    if score_match:
        ctx["score"] = int(score_match.group(1))

    # Extract rank (位次/排名)
    rank_match = re.search(r'(?:位次|排名|全省)\s*(\d{3,7})', msg)
    if rank_match:
        ctx["rank"] = int(rank_match.group(1))

    # Extract subject
    if "物理" in msg or "理科" in msg:
        ctx["subject_combo"] = "物理类"
    elif "历史" in msg or "文科" in msg:
        ctx["subject_combo"] = "历史类"
    elif "综合" in msg and ("改革" in msg or ctx["province"] in ["北京","天津","上海","浙江","山东","海南"]):
        ctx["subject_combo"] = "综合"

    # Extract desired location (期望省份/城市)
    loc_patterns = [
        r'(?:想去|想在|留在|只考虑|优先)\s*([一-鿿]{2,4}(?:省|市)?)',
        r'([一-鿿]{2,4})有哪些',
        r'(?:不去省外|就留本省|省内)',
    ]
    for ptn in loc_patterns:
        m = re.search(ptn, msg)
        if m:
            if "省外" in msg or "本省" in msg or "省内" in msg:
                if ctx.get("province"):
                    ctx["desired_location"] = ctx["province"]
            elif m.lastindex and m.lastindex >= 1:
                try:
                    ctx["desired_location"] = m.group(1)
                except IndexError:
                    pass
            break

    # Fall back to session history for missing fields
    if session_id and session_id != "new":
        history = session_store.get_context(session_id)
        for key in ctx:
            if not ctx[key]:
                ctx[key] = history.get(key)

    return {k: v for k, v in ctx.items() if v}  # Only non-empty


def _get_history_text(session_id):
    """Get recent conversation turns as formatted text."""
    if not session_id or session_id == "new":
        return ""
    try:
        turns = session_store.get_history(session_id, MAX_HISTORY_TURNS)
        if not turns:
            return ""
        lines = ["## 对话历史（最近几轮）"]
        for t in turns:
            role = "用户" if t.get("role") == "user" else "助手"
            content = (t.get("content") or "")[:300]
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
    except Exception:
        return ""


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
        logger.log_info("chat", "safety_pass", {"msg_len": len(msg)})
        if not check["safe"]:
            rm = REJECT.get(check["category"], "[安全提醒] 消息包含不适当内容。")
            yield await _sse("thinking", {"text": f"Safety: {check['category']}"})
            yield await _sse("token", {"text": rm})
            yield await _sse("done", {"thinking_time": round(time.time()-t0,2)})
            logger.log_warning("chat", "msg_blocked", category=check["category"])
            return

        # Validate or create session
        sid = session
        session_exists = False
        try:
            session_exists = session_store.session_exists(sid)
        except Exception:
            pass
        if not sid or sid == "new" or not session_exists:
            sid = session_store.create_session()
        logger.log_info("chat", "session_ready", {"sid": sid})

        # Extract user context BEFORE search (from msg + session history)
        context = _extract_context(msg, sid)
        logger.log_info("chat", "context_extracted", context)

        # Intent routing (skip LLM call for obvious volunteer queries)
        scene = "general"
        confidence = 0.3
        # Fast pre-check: if msg contains score + province/科类, it's volunteer
        has_score = bool(re.search(r'\d{3}\s*分', msg))
        has_location = bool(re.search(r'(?:河南|河北|山东|广东|江苏|四川|湖北|湖南|浙江|安徽|福建|江西|辽宁|陕西|山西|云南|贵州|广西|甘肃|吉林|黑龙江|内蒙古|新疆|海南|宁夏|青海|西藏|北京|上海|天津|重庆|物理|历史|文科|理科|综合|考生)', msg))
        if has_score and has_location:
            scene = "volunteer"
            confidence = 0.95
            logger.log_info("chat", "intent_fast_path", {"scene": scene})
        else:
            intent = classify_intent(lambda sp,um: _call_llm(sp,um), msg)
            scene = intent.get("scene", "general")
            confidence = intent.get("confidence", 0.3)
            logger.log_info("chat", "intent_llm", {"scene": scene, "confidence": f"{confidence:.2f}"})

        # Low confidence → fall back to general
        if confidence < INTENT_CONFIDENCE_THRESHOLD and scene != "general":
            logger.log_info("chat", "intent_low_confidence", {"scene": scene, "confidence": f"{confidence:.2f}"})
            scene = "general"

        yield await _sse("thinking", {"text": f"Intent: {scene} (confidence: {confidence:.2f})"})

        # Search with extracted context
        results = hybrid_search.search(msg, scene, context)
        sources = [r.get("content","")[:80] for r in results[:3]] if results else []
        yield await _sse("thinking", {"text": f"Found {len(results)} results", "sources": sources})

        # Get conversation history
        history_text = _get_history_text(sid)

        # Handler (pass context + history)
        logger.log_info("chat", "llm_start", {"scene": scene, "model": config.llm_primary_model or config.llm_fallback_model})
        handler = HANDLERS.get(scene, fb_h)
        response = handler(msg, context, results, history_text, lambda p,um=None: _call_llm(p,um))

        # Stream
        for i in range(0, len(response), 30):
            yield await _sse("token", {"text": response[i:i+30]})

        logger.log_info("chat", "response_done", {"len": len(response), "time": f"{time.time()-t0:.1f}s"})
        session_store.add_turn(sid, msg, response)
        yield await _sse("done", {"session_id": sid, "scene": scene, "thinking_time": round(time.time()-t0,2)})

    return EventSourceResponse(gen())


def _call_llm(sp, um=None):
    """Synchronous LLM call with primary to fallback retry."""
    import anthropic
    from openai import OpenAI

    if um is None:
        um = sp; sp = None

    def _detect(kind, model, base_url):
        if kind != "auto":
            return kind
        s = (model or "" + (base_url or "")).lower()
        if "claude" in s or "anthropic" in s:
            return "anthropic"
        return "openai"

    def _build(api_key, model, base_url, api_type):
        k = _detect(api_type, model, base_url or "")
        try:
            if k == "anthropic":
                c = anthropic.Anthropic(api_key=api_key, base_url=base_url or None, timeout=config.llm_timeout)
            else:
                c = OpenAI(api_key=api_key, base_url=base_url or None, timeout=config.llm_timeout)
            return (c, model, k)
        except Exception as e:
            logger.log_warning("llm", f"{k}_init_failed", detail={"error": str(e)})
            return None

    pairs = []
    if config.llm_primary_api_key:
        p = _build(config.llm_primary_api_key, config.llm_primary_model, config.llm_primary_base_url, config.llm_primary_api_type)
        if p: pairs.append(p)
    if config.llm_fallback_api_key:
        p = _build(config.llm_fallback_api_key, config.llm_fallback_model, config.llm_fallback_base_url, config.llm_fallback_api_type)
        if p: pairs.append(p)

    if not pairs:
        return "[系统提示] LLM 未配置，请在设置中填入 API Key。"

    last_error = ""
    logger.log_info("llm", "calling", {"kind": pairs[0][2], "model": pairs[0][1]})
    for client, model, kind in pairs:
        try:
            if kind == "anthropic":
                kw = {}
                if sp: kw["system"] = sp
                resp = client.messages.create(model=model, max_tokens=4096, messages=[{"role":"user","content":um}], **kw)
                logger.log_info("llm", "response_ok", {"kind": kind, "model": model})
                return resp.content[0].text
            else:
                msgs = []
                if sp: msgs.append({"role":"system","content":sp})
                msgs.append({"role":"user","content":um})
                resp = client.chat.completions.create(model=model, messages=msgs, max_tokens=4096, temperature=0.7)
                logger.log_info("llm", "response_ok", {"kind": kind, "model": model})
                return resp.choices[0].message.content
        except Exception as e:
            last_error = str(e)[:200]
            logger.log_warning("llm", f"{kind}_call_failed", detail={"error": last_error})
            if len(pairs) > 1:
                logger.log_info("llm", "switching_fallback", {"from": kind, "to": pairs[1][2]})
            continue

    logger.log_error("llm", "all_failed", Exception(last_error))
    return f"[系统提示] LLM 调用失败：{last_error}"
