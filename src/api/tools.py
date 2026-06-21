"""Tool endpoints - volunteer, quote, config."""
import os, json
from fastapi import APIRouter
from pydantic import BaseModel
from src.api.dependencies import session_store, hybrid_search, config, db
from src.agent.volunteer import handle as vol_h
from src.utils.prompt_templates import build_prompt
from src.retrieval.keyword_search import keyword_search

router = APIRouter(tags=["tools"])

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_FILE = os.path.join(_PROJECT_ROOT, ".env")

class VolunteerInput(BaseModel):
    province: str = "北京"; score: int = 600
    category: str = "物理类"; interests: str = ""

class QuoteInput(BaseModel):
    query: str; top_k: int = 5

@router.post("/tools/volunteer")
def volunteer_tool(data: VolunteerInput):
    if not data.province or not data.score:
        return {"error": "请至少填写省份和分数。"}
    query = f"{data.province}{data.category}{data.score}分 志愿填报推荐"
    if data.interests: query += f" 对{data.interests}感兴趣"
    context = {"province":data.province, "score":data.score, "category":data.category or "物理类",
               "interests":[i.strip() for i in data.interests.split(",") if i.strip()]}
    results = hybrid_search.search(query, "volunteer", context)
    prompt = build_prompt("volunteer", context)
    nl = chr(10)
    ctx = nl.join([f"[检索结果 {i+1}] {r['content']}" for i,r in enumerate(results[:8])])
    full = f"{prompt}{nl}{nl}## 检索相关信息{nl}{ctx}{nl}{nl}## 用户问题{nl}{query}"
    from src.api.chat import _call_llm
    resp = _call_llm(full)
    return {"query":query, "results_count":len(results), "response":resp,
            "sources":[r.get("content","")[:100] for r in results[:5]]}

@router.post("/tools/quote")
def quote_tool(data: QuoteInput):
    if not data.query or not data.query.strip():
        return {"error": "请输入搜索关键词。"}
    try:
        results = keyword_search(db, data.query, top_k=data.top_k)
    except Exception as e:
        return {"error": str(e)}
    if not results: return {"results":[], "message":"未找到相关语录。"}
    items = [{"source":r.get("source","未知"), "date":r.get("date","未知日期"),
              "content":r.get("content","")[:500], "topic":r.get("topic","")} for r in results]
    return {"results":items, "count":len(items)}

@router.get("/config")
def get_config():
    return {"llm_primary_model":config.llm_primary_model,
            "llm_primary_api_key":"***" if config.llm_primary_api_key else "",
            "llm_fallback_model":config.llm_fallback_model,
            "llm_fallback_api_key":"***" if config.llm_fallback_api_key else "",
            "embedding_mode":config.embedding_mode, "reranker_mode":config.reranker_mode,
            "gradio_port":config.gradio_port, "embedding_model":config.embedding_model}

class ConfigInput(BaseModel):
    llm_primary_api_key: str = ""; llm_primary_model: str = "claude-sonnet-4-6"
    llm_fallback_api_key: str = ""; llm_fallback_model: str = "deepseek-chat"
    embedding_api_key: str = ""; embedding_mode: str = "api"
    reranker_mode: str = "api"; gradio_port: int = 7860

@router.put("/config")
def save_config(data: ConfigInput):
    lines = ["# Zhang Xuefeng Agent - Environment Configuration", "",
             f"ZXF_LLM_PRIMARY_API_KEY={data.llm_primary_api_key}",
             f"ZXF_LLM_PRIMARY_MODEL={data.llm_primary_model}",
             f"ZXF_LLM_FALLBACK_API_KEY={data.llm_fallback_api_key}",
             f"ZXF_LLM_FALLBACK_MODEL={data.llm_fallback_model}",
             f"ZXF_EMBEDDING_API_KEY={data.embedding_api_key}",
             f"ZXF_EMBEDDING_MODE={data.embedding_mode}",
             f"ZXF_RERANKER_MODE={data.reranker_mode}",
             f"ZXF_GRADIO_PORT={data.gradio_port}", ""]
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        f.write(chr(10).join(lines))
    return {"ok": True}
