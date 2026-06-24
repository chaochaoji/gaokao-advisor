# LLM client with streaming support
from src.api.dependencies import config, logger

def call_llm(sp, um=None):
    result=[]
    for token in stream_llm(sp, um):
        result.append(token)
    return "".join(result)

def stream_llm(sp, um=None):
    import anthropic
    from openai import OpenAI
    if um is None:
        um = sp; sp = None

    def _detect(kind, model, base_url):
        if kind != "auto": return kind
        s = (model + base_url).lower()
        if "claude" in s or "anthropic" in s: return "anthropic"
        return "openai"

    def _build(api_key, model, base_url, api_type):
        k = _detect(api_type, model, base_url or "")
        if k == "openai" and not base_url and "deepseek" in model.lower():
            base_url = "https://api.deepseek.com/v1"
        try:
            if k == "anthropic":
                cl = anthropic.Anthropic(api_key=api_key, base_url=base_url or None, timeout=config.llm_timeout)
            else:
                cl = OpenAI(api_key=api_key, base_url=base_url, timeout=config.llm_timeout)
            return (cl, model, k)
        except Exception as e:
            logger.log_warning("llm", f"{k}_init_failed", detail={"error": str(e)})
            return None
    pairs = []


    pairs = []
    if config.llm_primary_api_key:
        p = _build(config.llm_primary_api_key, config.llm_primary_model, config.llm_primary_base_url, config.llm_primary_api_type)
        if p: pairs.append(p)
    if config.llm_fallback_api_key:
        p = _build(config.llm_fallback_api_key, config.llm_fallback_model, config.llm_fallback_base_url, config.llm_fallback_api_type)
        if p: pairs.append(p)
    if not pairs:
        yield "[系统提示] LLM 未配置。"
        return
    logger.log_info("llm", "calling", {"kind": pairs[0][2], "model": pairs[0][1]})
    last_err = ""
    for client, model, kind in pairs:
        try:
            if kind == "anthropic":
                kw = {}
                if sp: kw["system"] = sp
                with client.messages.stream(model=model, max_tokens=2048, messages=[{"role":"user","content":um}], **kw) as s:
                    for text in s.text_stream:
