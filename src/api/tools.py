"""Tool endpoints - volunteer, quote, config."""
import os, json, re
from fastapi import APIRouter
from pydantic import BaseModel
from src.api.dependencies import session_store, hybrid_search, config, db
from src.agent.volunteer import handle as vol_h
from src.utils.prompt_templates import build_prompt
from src.retrieval.keyword_search import keyword_search

# ---- Volunteer assessment JSON validation & fallback parsing ----
_REQUIRED_TOP_FIELDS = {
    "summary": dict, "schools": list, "risks": list,
    "data_year": str, "data_sources": list, "major_analysis": dict
}
_REQUIRED_SCHOOL_FIELDS = {
    "name": str, "city": str, "type": str, "tier": str,
    "majors": list, "min_score": int, "min_rank": int,
    "reason": str, "tags": list, "risk_note": str
}
_VALID_TIERS = {"冲刺", "稳妥", "保底"}


def _validate_and_parse_volunteer_json(raw_text: str, user_ctx: dict) -> dict:
    """Try to parse LLM output as JSON, with fallback extraction."""
    text = raw_text.strip()
    parsed = None

    # Strip markdown code block fences
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        text = "\n".join(lines)

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try extracting a JSON object from text
    if parsed is None:
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except (json.JSONDecodeError, ValueError):
                pass

    # Validate top-level fields
    if parsed:
        valid = True
        for field, typ in _REQUIRED_TOP_FIELDS.items():
            if field not in parsed or not isinstance(parsed[field], typ):
                valid = False
                break
        if valid and parsed.get("schools"):
            for s in parsed["schools"]:
                s["tier"] = s.get("tier", "稳妥")
                if s["tier"] not in _VALID_TIERS:
                    s["tier"] = "稳妥"
                # 确保整数类型
                if not isinstance(s.get("min_score"), int):
                    try:
                        s["min_score"] = int(s["min_score"])
                    except (ValueError, TypeError):
                        s["min_score"] = 0
                if not isinstance(s.get("min_rank"), int):
                    try:
                        s["min_rank"] = int(s["min_rank"])
                    except (ValueError, TypeError):
                        s["min_rank"] = 0
        if valid and len(parsed.get("schools", [])) > 0:
            return {"ok": True, "data": parsed}

    # Fallback: regex extraction of school list
    schools_raw = re.findall(
        r'(?:推荐|报考).*?(\S{2,8}(?:大学|学院)).*?(\d{3})\s*分.*?(\d{3,7})\s*(?:名|位)',
        text
    )
    if schools_raw:
        schools = []
        for name, score, rank in schools_raw[:8]:
            schools.append({
                "name": name, "city": "", "type": "",
                "tier": "稳妥", "majors": [],
                "min_score": int(score), "min_rank": int(rank),
                "reason": "", "tags": [], "risk_note": ""
            })
        fallback_data = {
            "summary": {
                "position": "位次估算中",
                "score": user_ctx.get("score", 0),
                "rank": 0, "rank_range": [0, 0],
                "advice": "以下为自动提取的院校列表，建议重新生成获取完整报告"
            },
            "schools": schools,
            "major_analysis": {
                "summary": "", "pros": [], "cons": [], "grad_school_rate": ""
            },
            "risks": ["数据提取不完整，建议重新生成"],
            "data_year": "", "data_sources": []
        }
        return {"ok": True, "data": fallback_data, "fallback": True}

    return {"ok": False, "raw": text}


router = APIRouter(tags=["tools"])

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_FILE = os.path.join(_PROJECT_ROOT, ".env")

class VolunteerInput(BaseModel):
    province: str = "北京"; score: int = 600; rank: int = 0
    category: str = "物理类"; interests: str = ""
    desired_location: str = ""; session_id: str = ""

class QuoteInput(BaseModel):
    query: str; top_k: int = 5

@router.post("/tools/volunteer")
def volunteer_tool(data: VolunteerInput):
    if not data.province or not data.score:
        return {"error": "请至少填写省份和分数。"}
    query = f"{data.province}{data.category}{data.score}分"
    if data.rank: query += f" 位次{data.rank}"
    query += " 志愿填报推荐"
    if data.interests: query += f" 对{data.interests}感兴趣"
    if data.desired_location: query += f" 期望地区{data.desired_location}"

    context = {"province":data.province, "score":data.score, "category":data.category or "物理类",
               "interests":[i.strip() for i in data.interests.split(",") if i.strip()],
               "rank":data.rank, "desired_location":data.desired_location}
    results = hybrid_search.search(query, "volunteer", context)

    # 使用 volunteer_form prompt（含 JSON 输出指令）
    prompt = build_prompt("volunteer_form", context)

    # 构建检索数据 + 用户信息
    nl = chr(10)
    ctx = nl.join([f"[检索结果 {i+1}] {r['content']}" for i,r in enumerate(results[:10])])
    user_info_lines = [f"省份: {data.province}, 科类: {data.category}, 分数: {data.score}"]
    if data.rank: user_info_lines.append(f"位次: {data.rank}")
    if data.interests: user_info_lines.append(f"意向专业: {data.interests}")
    if data.desired_location:
        user_info_lines.append(f"期望地区: {data.desired_location}（优先推荐该地区）")
    else:
        user_info_lines.append("期望地区: 未指定（全国范围推荐）")

    full_prompt = f"{prompt}{nl}{nl}## 检索到的数据{nl}{ctx}{nl}{nl}## 用户信息{nl}{nl.join(user_info_lines)}{nl}{nl}请按 JSON 格式输出完整的志愿评估报告。切记只输出 JSON，不要包含任何其他文本。"

    from src.api.chat import _call_llm
    resp = _call_llm(full_prompt)

    # 校验 + fallback
    user_ctx = {"score": data.score, "rank": data.rank, "province": data.province}
    result = _validate_and_parse_volunteer_json(resp, user_ctx)

    # 创建或使用已有 session
    sid = data.session_id if data.session_id else session_store.create_session()
    user_msg = f"[志愿评估] {data.province}{data.category}{data.score}分"
    if data.interests: user_msg += f" 意向{data.interests}"
    if data.desired_location: user_msg += f" 期望{data.desired_location}"

    if result["ok"]:
        # 结构化存储
        session_store.add_turn(sid, user_msg, {
            "content_type": "volunteer_assessment",
            "structured_data": result["data"],
            "fallback_text": resp
        })
        return {
            "ok": True,
            "session_id": sid,
            "structured_data": result["data"],
            "fallback": result.get("fallback", False),
            "sources": [r.get("content","")[:100] for r in results[:5]]
        }
    else:
        # 解析失败，退化为纯文本存储
        session_store.add_turn(sid, user_msg, resp)
        return {
            "ok": True,
            "session_id": sid,
            "fallback_text": resp,
            "parse_error": True,
            "sources": [r.get("content","")[:100] for r in results[:5]]
        }

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
            "llm_primary_api_key": config.llm_primary_api_key or "",
            "llm_primary_api_type": config.llm_primary_api_type,
            "llm_primary_base_url": config.llm_primary_base_url,
            "llm_fallback_model":config.llm_fallback_model,
            "llm_fallback_api_key": config.llm_fallback_api_key or "",
            "llm_fallback_api_type": config.llm_fallback_api_type,
            "llm_fallback_base_url": config.llm_fallback_base_url,
            "embedding_api_key": config.embedding_api_key or "",
            "embedding_mode":config.embedding_mode, "reranker_mode":config.reranker_mode,
            "gradio_port":config.gradio_port, "embedding_model":config.embedding_model}

class ConfigInput(BaseModel):
    llm_primary_api_key: str = ""; llm_primary_model: str = "deepseek-v4-pro"
    llm_primary_api_type: str = "auto"; llm_primary_base_url: str = ""
    llm_fallback_api_key: str = ""; llm_fallback_model: str = "deepseek-v4-pro"
    llm_fallback_api_type: str = "auto"; llm_fallback_base_url: str = ""
    embedding_api_key: str = ""; embedding_mode: str = "api"
    reranker_mode: str = "api"; gradio_port: int = 7860

@router.put("/config")
def save_config(data: ConfigInput):
    lines = ["# Zhang Xuefeng Agent - Environment Configuration", "",
             f"ZXF_LLM_PRIMARY_API_KEY={data.llm_primary_api_key}",
             f"ZXF_LLM_PRIMARY_MODEL={data.llm_primary_model}",
             f"ZXF_LLM_PRIMARY_API_TYPE={data.llm_primary_api_type}",
             f"ZXF_LLM_PRIMARY_BASE_URL={data.llm_primary_base_url}",
             f"ZXF_LLM_FALLBACK_API_KEY={data.llm_fallback_api_key}",
             f"ZXF_LLM_FALLBACK_MODEL={data.llm_fallback_model}",
             f"ZXF_LLM_FALLBACK_API_TYPE={data.llm_fallback_api_type}",
             f"ZXF_LLM_FALLBACK_BASE_URL={data.llm_fallback_base_url}",
             f"ZXF_EMBEDDING_API_KEY={data.embedding_api_key}",
             f"ZXF_EMBEDDING_MODE={data.embedding_mode}",
             f"ZXF_RERANKER_MODE={data.reranker_mode}",
             f"ZXF_GRADIO_PORT={data.gradio_port}", ""]
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        f.write(chr(10).join(lines))

    # Hot-reload: update environment and in-memory config immediately
    import os
    os.environ["ZXF_LLM_PRIMARY_API_KEY"] = data.llm_primary_api_key
    os.environ["ZXF_LLM_PRIMARY_MODEL"] = data.llm_primary_model
    os.environ["ZXF_LLM_PRIMARY_API_TYPE"] = data.llm_primary_api_type
    os.environ["ZXF_LLM_PRIMARY_BASE_URL"] = data.llm_primary_base_url
    os.environ["ZXF_LLM_FALLBACK_API_KEY"] = data.llm_fallback_api_key
    os.environ["ZXF_LLM_FALLBACK_MODEL"] = data.llm_fallback_model
    os.environ["ZXF_LLM_FALLBACK_API_TYPE"] = data.llm_fallback_api_type
    os.environ["ZXF_LLM_FALLBACK_BASE_URL"] = data.llm_fallback_base_url
    os.environ["ZXF_EMBEDDING_API_KEY"] = data.embedding_api_key
    os.environ["ZXF_EMBEDDING_MODE"] = data.embedding_mode
    os.environ["ZXF_RERANKER_MODE"] = data.reranker_mode
    os.environ["ZXF_GRADIO_PORT"] = str(data.gradio_port)

    from src.config import load_config
    fresh = load_config(load_env_file=False)
    for field_name in config.__dataclass_fields__:
        setattr(config, field_name, getattr(fresh, field_name))

    return {"ok": True}
