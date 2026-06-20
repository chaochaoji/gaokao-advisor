# -*- coding: utf-8 -*-
"""Gradio Web UI for the Zhang Xuefeng Knowledge Distillation Agent."""
from __future__ import annotations

import os
import sys
import json
import time
import re
from typing import Generator, Optional

import gradio as gr

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC_ROOT = os.path.join(_PROJECT_ROOT, 'src')
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

from src.config import load_config
from src.knowledge.sqlite_store import get_db, init_db
from src.knowledge.chroma_store import get_chroma_collection
from src.retrieval.embedding_service import EmbeddingService
from src.retrieval.reranker import RerankerService
from src.retrieval.hybrid_search import HybridSearch
from src.agent.router import classify_intent
from src.agent.volunteer import handle as volunteer_handle
from src.agent.opinion import handle as opinion_handle
from src.agent.style_chat import handle as style_chat_handle
from src.agent.fallback import handle as fallback_handle
from src.safety.input_gateway import InputSafetyGateway
from src.utils.logger import AgentLogger
from src.utils.conversation import ConversationManager


# ============================================================================
# Configuration and Service Initialization
# ============================================================================

config = load_config()
logger = AgentLogger(config.log_dir, session_id='gradio')

db = get_db(config)
init_db(db)
logger.log_info('sqlite', 'db_initialized', {'path': config.sqlite_path})

chroma_col = get_chroma_collection(config)
chroma_count = len(chroma_col._ids) if hasattr(chroma_col, '_ids') else 'unknown'
logger.log_info('chromadb', 'collection_loaded', {'count': chroma_count})

embedding_svc = EmbeddingService(
    mode="auto",
    api_key=config.embedding_api_key,
    model=config.embedding_model,
    local_path=config.embedding_local_path,
)
logger.log_info('embedding', 'service_initialized', {'mode': embedding_svc.mode, 'device': embedding_svc.device_info})

reranker = RerankerService(
    mode="auto",
    model=config.reranker_model,
)
logger.log_info('reranker', 'service_initialized', {'mode': config.reranker_mode})

hybrid_search = HybridSearch(
    mode='prod',
    embedding_svc=embedding_svc,
    chroma_col=chroma_col,
    db_conn=db,
    reranker=reranker,
    logger=logger,
)
logger.log_info('hybrid_search', 'service_initialized')

safety = InputSafetyGateway()
conversation = ConversationManager()
logger.log_info('safety', 'gateway_initialized')
logger.log_info('conversation', 'manager_initialized')

# ============================================================================
# LLM Client
# ============================================================================

def _build_llm_client():
    primary = None
    fallback = None

    if config.llm_primary_api_key:
        try:
            import anthropic
            primary = anthropic.Anthropic(
                api_key=config.llm_primary_api_key,
                base_url=config.llm_primary_base_url or None,
                timeout=config.llm_timeout,
            )
            logger.log_info(
                'llm', 'primary_client_ready',
                {'model': config.llm_primary_model},
            )
        except Exception as e:
            logger.log_error(
                'llm', 'primary_client_init_failed', e,
                fallback_action='use_fallback_only',
            )
    else:
        logger.log_info('llm', 'primary_skipped', {'reason': 'no_api_key'})

    if config.llm_fallback_api_key:
        try:
            from openai import OpenAI
            fallback = OpenAI(
                api_key=config.llm_fallback_api_key,
                base_url=config.llm_fallback_base_url,
                timeout=config.llm_timeout,
            )
            logger.log_info('llm', 'fallback_client_ready',
                {'model': config.llm_fallback_model},
            )
        except Exception as e:
            logger.log_error(
                'llm', 'fallback_client_init_failed', e,
                fallback_action='no_llm_available',
            )
    else:
        logger.log_info('llm', 'fallback_skipped', {'reason': 'no_api_key'})

    return primary, fallback


(llm_primary, llm_fallback) = _build_llm_client()


# ============================================================================
# Unified LLM Call Interface
# ============================================================================

REJECT_MESSAGES = {
    "jailbreak": "[安全提醒] 你的消息包含不被允许的指令，请重新描述你的问题。",
    "privacy": "[安全提醒] 请勿查询他人隐私信息。",
    "abuse": "[安全提醒] 请使用文明用语交流。",
    "regional_attack": "[安全提醒] 地域攻击言论不被允许。",
}


def call_llm_sync(prompt_or_system, user_msg=None):
    """Non-streaming LLM call. Returns full response string."""
    if user_msg is not None:
        system_prompt = prompt_or_system
        user_content = user_msg
    else:
        system_prompt = None
        user_content = prompt_or_system

    client = llm_primary or llm_fallback
    if client is None:
        return "[系统提示] LLM 客户端未配置，请在 .env 中设置 API key。"

    using_primary = bool(llm_primary)
    model = config.llm_primary_model if using_primary else config.llm_fallback_model

    try:
        return _call_anthropic_sync(client, model, system_prompt, user_content)
    except Exception as e:
        logger.log_error(
            "llm" if using_primary else "llm_fallback",
            "sync_call_failed", e,
            fallback_action="retry_with_fallback",
        )
        if using_primary and llm_fallback:
            try:
                return _call_openai_sync(llm_fallback, config.llm_fallback_model, system_prompt, user_content)
            except Exception as e2:
                logger.log_error("llm_fallback", "fallback_sync_failed", e2)
        return "[系统提示] LLM 调用失败，请稍后重试。"


def _call_anthropic_sync(client, model, system_prompt, user_content):
    """Synchronous call to Anthropic API."""
    kwargs = {}
    messages = []
    if system_prompt:
        kwargs["system"] = system_prompt
    messages.append({"role": "user", "content": user_content})
    resp = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=messages,
        **kwargs,
    )
    return resp.content[0].text


def _call_openai_sync(client, model, system_prompt, user_content):
    """Synchronous call to OpenAI-compatible API (DeepSeek)."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=2048,
        temperature=0.7,
    )
    return resp.choices[0].message.content

# ============================================================================
# Main Chat Function (Gradio streaming generator)
# ============================================================================


def chat_fn(message, history):
    # Main chat orchestrator: safety -> reference resolution -> intent
    # -> search -> scene handler -> streaming response.
    # --- Safety check ---
    check_result = safety.check(message)
    if not check_result['safe']:
        reject_msg = REJECT_MESSAGES.get(check_result['category'],
            '[安全提醒] 你的消息包含不适当内容。')
        logger.log_warning('safety', 'message_blocked',
            {'category': check_result['category'], 'reason': check_result['reason']})
        yield reject_msg
        return

    # --- Reference resolution ---
    resolved_message = conversation.resolve_references(message)

    # --- Intent routing ---
    def _router_llm(system_prompt, user_msg):
        return call_llm_sync(system_prompt, user_msg)
    intent = classify_intent(_router_llm, resolved_message)
    scene = intent.get('scene', 'general')
    confidence = intent.get('confidence', 0.3)
    logger.log_info('router', 'intent_classified',
        {'scene': scene, 'confidence': confidence, 'query': resolved_message[:80]})

    # --- Hybrid search ---
    ctx = conversation.get_context()
    search_results = hybrid_search.search(resolved_message, scene, ctx.get('context_state', {}))
    logger.log_info('hybrid_search', 'search_complete', {'count': len(search_results)})

    # --- Scene handler ---
    handlers = {
        'volunteer': volunteer_handle,
        'opinion': opinion_handle,
        'style_chat': style_chat_handle,
        'general': fallback_handle,
    }
    handler = handlers.get(scene, fallback_handle)

    # Build the llm_call closure for handlers
    def _handler_llm(prompt_or_system, user_msg=None):
        return call_llm_sync(prompt_or_system, user_msg)

    response_text = handler(resolved_message, ctx.get('context_state', {}),
        search_results, _handler_llm)

    # Stream the response character by character for Gradio
    # (Full string returned by handler, streamed as chunks)
    chunk_size = 30
    for i in range(0, len(response_text), chunk_size):
        yield response_text[i:i + chunk_size]

    # --- Save conversation turn ---
    conversation.add_turn(message, response_text)


# ============================================================================
# 志愿评估 Form Handler
# ============================================================================


def volunteer_form_fn(province, score, category, interests):
    # Take structured form input and run the volunteer assessment pipeline.
    if not province or not score:
        yield "请至少填写省份和分数。"
        return

    query = f"{province}{category}{score}分 志愿填报推荐"
    if interests:
        query += f" 对{interests}感兴趣"

    # Build context from form fields
    context = {
        "province": province,
        "score": score,
        "category": category or "物理类",
        "interests": [i.strip() for i in interests.split(",") if i.strip()],
    }

    # Search
    search_results = hybrid_search.search(query, "volunteer", context)

    # Build prompt and call LLM
    from src.utils.prompt_templates import build_prompt
    prompt = build_prompt("volunteer", context)
    context_str = "\n".join(
        [f"[检索结果 {i+1}] {r['content']}" for i, r in enumerate(search_results[:8])]
    )
    full_prompt = f"{prompt}\n\n## 检索到的相关信息\n{context_str}\n\n## 用户问题\n{query}"

    response_text = call_llm_sync(full_prompt)

    # Stream response
    chunk_size = 30
    for i in range(0, len(response_text), chunk_size):
        yield response_text[i:i + chunk_size]


# ============================================================================
# 语录搜索 Handler
# ============================================================================


def quote_search_fn(query, top_k):
    # Full-text search over the corpus for quotes.
    if not query or not query.strip():
        return "请输入搜索关键词。"

    try:
        from src.retrieval.keyword_search import keyword_search
        results = keyword_search(db, query, top_k=int(top_k))
    except Exception as e:
        return f"搜索失败: {e}"

    if not results:
        return "未找到相关语录，请尝试其他关键词。"

    # Format as readable text
    lines_out = []
    for i, r in enumerate(results):
        source = r.get("source", "未知")
        date = r.get("date", "未知日期")
        content = r.get("content", "")[:500]
        topic = r.get("topic", "")
        lines_out.append(f"### 结果 {i+1} | {source} | {date}")
        if topic:
            lines_out.append(f"*主题: {topic}*")
        lines_out.append(content)
        lines_out.append("")
    return "\n".join(lines_out)


# ============================================================================
# Health Status Check
# ============================================================================


def get_health_status():
    # Probe each service and return a status dict.
    status = {}

    # SQLite
    try:
        db.execute("SELECT 1")
        status['数据库'] = '正常'
    except Exception as e:
        status['数据库'] = f'异常: {e}'

    # ChromaDB / NumpyCollection
    try:
        count = len(chroma_col._ids) if hasattr(chroma_col, '_ids') else '?'
        status['知识库'] = f'正常 ({count} 条)'
    except Exception as e:
        status['知识库'] = f'异常: {e}'

    # Embedding
    status['向量模型'] = f'正常 ({embedding_svc.mode}, {embedding_svc.device_info})'

    # Reranker
    status['重排序'] = f'正常 (mode={config.reranker_mode})'

    # LLM Primary
    if llm_primary:
        status['主模型'] = f'正常 ({config.llm_primary_model})'
    else:
        status['主模型'] = '未配置'

    # LLM Fallback
    if llm_fallback:
        status['备用模型'] = f'正常 ({config.llm_fallback_model})'
    else:
        status['备用模型'] = '未配置'

    return status


def get_health_markdown():
    # Render health status as markdown table.
    status = get_health_status()
    lines_md = ["| 服务 | 状态 |", "|------|------|"]
    for svc, st in status.items():
        emoji = '✅' if st.startswith('正常') else '⚠️'
        lines_md.append(f'| {svc} | {emoji} {st} |')
    return "\n".join(lines_md)



# ============================================================================
# Gradio UI
# ============================================================================
SETTINGS_FILE = os.path.join(_PROJECT_ROOT, '.env')
def load_settings():
    settings = {}
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    settings[key.strip()] = val.strip()
    return settings
def save_settings(llm_primary_key, llm_primary_model,
                  llm_fallback_key, llm_fallback_model,
                  embedding_key, embedding_mode,
                  reranker_mode, gradio_port):
    lines = [
        '# Zhang Xuefeng Agent - Environment Configuration',
        '# Generated from Settings panel',
        '',
        f'ZXF_LLM_PRIMARY_API_KEY={llm_primary_key}',
        f'ZXF_LLM_PRIMARY_MODEL={llm_primary_model}',
        f'ZXF_LLM_FALLBACK_API_KEY={llm_fallback_key}',
        f'ZXF_LLM_FALLBACK_MODEL={llm_fallback_model}',
        f'ZXF_EMBEDDING_API_KEY={embedding_key}',
        f'ZXF_EMBEDDING_MODE={embedding_mode}',
        f'ZXF_RERANKER_MODE={reranker_mode}',
        f'GRADIO_PORT={gradio_port}',
        '',
    ]
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        f.write(chr(10).join(lines))
    return '配置已保存到 .env 文件！请重启服务使配置生效。'
def get_current_settings():
    s = load_settings()
    return [
        s.get('ZXF_LLM_PRIMARY_API_KEY', ''),
        s.get('ZXF_LLM_PRIMARY_MODEL', config.llm_primary_model),
        s.get('ZXF_LLM_FALLBACK_API_KEY', ''),
        s.get('ZXF_LLM_FALLBACK_MODEL', config.llm_fallback_model),
        s.get('ZXF_EMBEDDING_API_KEY', ''),
        s.get('ZXF_EMBEDDING_MODE', config.embedding_mode),
        s.get('ZXF_RERANKER_MODE', config.reranker_mode),
        s.get('GRADIO_PORT', str(config.gradio_port)),
    ]


def create_ui():
    import gradio as gr
    custom_css = (
        '.health-ok { color: #22c55e; } '
        '.health-warn { color: #eab308; }'
    )
    with gr.Blocks(title='张雪峰知识蒸馏 Agent') as demo:
        gr.Markdown('# 张雪峰知识蒸馏 Agent')
        gr.Markdown('基于张雪峰老师公开言论与教育数据构建的 AI 教育规划助手。')
        with gr.Accordion('系统状态', open=False):
            health_md = gr.Markdown(value=get_health_markdown(), every=30)
        with gr.Tabs():
            with gr.TabItem('智能问答'):
                qa_chatbot = gr.Chatbot(height=550, label='对话')
                qa_input = gr.Textbox(placeholder='输入你的问题，如：河南理科580分计算机推荐什么学校...', label='你的问题', scale=4)
                with gr.Row():
                    qa_submit = gr.Button('发送', variant='primary')
                    qa_clear = gr.Button('清空')
                qa_submit.click(fn=chat_fn, inputs=[qa_input, qa_chatbot], outputs=[qa_chatbot])
                qa_input.submit(fn=chat_fn, inputs=[qa_input, qa_chatbot], outputs=[qa_chatbot])
                qa_clear.click(lambda: ([], ''), None, [qa_chatbot, qa_input])
            # Tab 2: 志愿评估
            with gr.TabItem('志愿评估'):
                gr.Markdown('### 高考志愿评估工具')
                gr.Markdown('填写以下信息，获取个性化院校和专业推荐。')
                with gr.Row():
                    vf_province = gr.Dropdown(choices=['北京','上海','广东','浙江','江苏','四川','湖北','山东','河南','河北','福建','其他'], label='省份', value='北京')
                    vf_score = gr.Number(label='分数', minimum=0, maximum=750, value=600)
                    vf_category = gr.Radio(choices=['物理类','历史类'], label='科类', value='物理类')
                vf_interests = gr.Textbox(label='意向专业（逗号分隔）', placeholder='如：计算机、医学、金融')
                with gr.Row():
                    vf_submit = gr.Button('开始评估', variant='primary')
                    vf_clear = gr.Button('清空')
                vf_output = gr.Textbox(label='评估结果', lines=15, interactive=False)
                vf_submit.click(fn=volunteer_form_fn, inputs=[vf_province, vf_score, vf_category, vf_interests], outputs=[vf_output])
                vf_clear.click(lambda: ('北京',600,'物理类','',''), None, [vf_province, vf_score, vf_category, vf_interests, vf_output])
            # Tab 3: 语录搜索
            with gr.TabItem('语录搜索'):
                gr.Markdown('### 张雪峰语录搜索')
                gr.Markdown('搜索张雪峰老师在直播、演讲、文章中的相关语录。')
                with gr.Row():
                    qs_query = gr.Textbox(label='搜索关键词', placeholder='输入关键词...', scale=4)
                    qs_top_k = gr.Slider(minimum=1, maximum=20, value=5, step=1, label='返回条数')
                qs_submit = gr.Button('搜索', variant='primary')
                qs_output = gr.Markdown()
                qs_submit.click(fn=quote_search_fn, inputs=[qs_query, qs_top_k], outputs=[qs_output])
            with gr.TabItem('系统设置'):
                gr.Markdown('### 服务配置')
                gr.Markdown('修改配置后点击保存，然后重启服务使配置生效。')
                with gr.Row():
                    s_pk = gr.Textbox(label='主模型 API Key', placeholder='sk-ant-...', type='password')
                    s_pm = gr.Textbox(label='主模型名称', value=config.llm_primary_model)
                with gr.Row():
                    s_fk = gr.Textbox(label='备用模型 API Key', placeholder='sk-...', type='password')
                    s_fm = gr.Textbox(label='备用模型名称', value=config.llm_fallback_model)
                with gr.Row():
                    s_ek = gr.Textbox(label='Embedding API Key', placeholder='sk-...', type='password')
                    s_em = gr.Radio(choices=['auto', 'api', 'local', 'cpu'], label='Embedding 模式', value='auto')
                with gr.Row():
                    s_rm = gr.Radio(choices=['api', 'local', 'mock'], label='Reranker 模式', value=config.reranker_mode)
                    s_pt = gr.Number(label='服务端口', value=config.gradio_port, precision=0)
                with gr.Row():
                    s_save = gr.Button('保存配置', variant='primary')
                    s_load = gr.Button('加载当前配置')
                s_msg = gr.Markdown('')
                s_load.click(fn=get_current_settings, inputs=[], outputs=[s_pk, s_pm, s_fk, s_fm, s_ek, s_em, s_rm, s_pt])
                s_save.click(fn=save_settings, inputs=[s_pk, s_pm, s_fk, s_fm, s_ek, s_em, s_rm, s_pt], outputs=[s_msg])
    return demo

if __name__ == '__main__':
    demo = create_ui()
    demo.launch(server_port=config.gradio_port, share=config.gradio_share,
                css='.health-ok { color: #22c55e; } .health-warn { color: #eab308; }')
