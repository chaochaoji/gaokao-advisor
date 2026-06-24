// chat.js
function addUserMessage(text) {
    var div = document.createElement("div");
    div.className = "message-row user";
    div.innerHTML = '<div class="message-bubble user">' + escapeHtml(text) + '</div>';
    el("#chat-messages").appendChild(div);
    scrollToBottom();
}

function createAgentSkeleton() {
    var div = document.createElement("div");
    div.className = "message-row agent agent-skeleton";
    div.innerHTML = '<div class="message-avatar">助手</div>'
        + '<div class="message-content">'
        + '<div class="think-block">'
        + '<div class="think-header"><span class="think-arrow">&#9654;</span> 思考中...</div>'
        + '<div class="think-body"></div></div>'
        + '<div class="message-bubble agent"><span class="response-text"></span></div>'
        + '<div class="message-meta"><button class="copy-btn" title="复制"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg></button></div></div>';
    el("#chat-messages").appendChild(div);
    return div;
}

function updateThinking(bubble, text) {
    var think = bubble.querySelector(".think-body");
    if (think) think.textContent = text;
    scrollToBottom();
}

// Timer state stored per bubble
function startThinkingTimer(bubble) {
    var start = Date.now();
    bubble._thinkStart = start;
    bubble._thinkTimer = setInterval(function () {
        var elapsed = Math.floor((Date.now() - start) / 1000);
        var header = bubble.querySelector(".think-header");
        if (!header) return;
        var timeStr = elapsed >= 60
            ? Math.floor(elapsed / 60) + 'm ' + (elapsed % 60) + 's'
            : elapsed + 's';
        header.innerHTML = '<span class="think-arrow">&#9654;</span> 思考中... ' + timeStr;
    }, 500);
}

function finalizeThinking(bubble, time) {
    // Stop live timer
    if (bubble._thinkTimer) { clearInterval(bubble._thinkTimer); bubble._thinkTimer = null; }
    var elapsed = bubble._thinkStart ? Math.floor((Date.now() - bubble._thinkStart) / 1000) : (time || 0);
    var timeStr = elapsed >= 60
        ? Math.floor(elapsed / 60) + 'm ' + (elapsed % 60) + 's'
        : elapsed + 's';
    var header = bubble.querySelector(".think-header");
    if (header) header.innerHTML = '<span class="think-arrow">&#9654;</span> 已思考完(用时 ' + timeStr + ')';
    var tb = bubble.querySelector(".think-block");
    if (tb) tb.querySelector(".think-header").addEventListener("click", function () {
        tb.classList.toggle("expanded");
    });
}

function appendToken(bubble, text) {
    var resp = bubble.querySelector(".response-text");
    if (resp) resp.textContent += text;
    scrollToBottom();
}

function finalizeMessage(bubble) {
    bubble.classList.remove("agent-skeleton");
    var btn = bubble.querySelector(".copy-btn");
    if (btn) btn.addEventListener("click", function () {
        var resp = bubble.querySelector(".response-text");
        if (resp) copyToClipboard(resp.textContent, btn);
    });
}

function scrollToBottom() {
    var mc = el("#chat-messages");
    if (mc) mc.scrollTop = mc.scrollHeight;
}

function renderMessages(msgs) {
    msgs.forEach(function (m) {
        if (m.role === "user") {
            addUserMessage(m.content);
        } else if (m.role === "assistant") {
            if (m.content_type === 'volunteer_assessment' && m.metadata) {
                // 结构化评估结果 → 渲染卡片
                addVolunteerResultMessage(m.metadata, m.content);
            } else {
                // 普通文本消息
                var bubble = createAgentSkeleton();
                var resp = bubble.querySelector(".response-text");
                if (resp) resp.innerHTML = renderMarkdown(m.content);
                bubble.classList.remove("agent-skeleton");
                finalizeMessage(bubble);
            }
        }
    });
    scrollToBottom();
}

function addVolunteerResultMessage(structuredData, fallbackText) {
    var div = document.createElement("div");
    div.className = "message-row agent";
    div.innerHTML = '<div class="message-avatar">助手</div>'
        + '<div class="message-content"><div id="volunteer-result-inline"></div></div>';
    el("#chat-messages").appendChild(div);

    // 渲染到临时容器
    var container = div.querySelector("#volunteer-result-inline");
    container.id = ''; // 去掉 id 避免重复

    if (structuredData && structuredData.schools) {
        renderVolunteerResultToContainer(container, structuredData);
    } else if (fallbackText) {
        container.innerHTML = renderMarkdown(fallbackText);
    }
    scrollToBottom();
}

function lockInput() {
    var input = el("#msg-input");
    var btn = el("#send-btn");
    if (input) { input.disabled = true; input.placeholder = "AI 回复中，请稍候..."; }
    if (btn) btn.disabled = true;
}
function unlockInput() {
    var input = el("#msg-input");
    var btn = el("#send-btn");
    if (input) { input.disabled = false; input.placeholder = "输入你的问题..."; }
    if (btn) btn.disabled = false;
    el("#msg-input").focus();
}

function onSendMessage() {
    var input = el("#msg-input");
    var msg = input.value.trim();
    if (!msg) return;
    input.value = "";
    lockInput();

    var state = window.sidebarState || {};
    if (!state.currentSessionId || state.currentSessionId === "new") {
        createSession().then(function (data) {
            if (window.sidebarState) window.sidebarState.currentSessionId = data.id;
            renderSessionList();
            streamMessage(msg);
        }).catch(function (e) {
            showToast("创建会话失败: " + (e.message || "未知错误"));
            unlockInput();
        });
    } else {
        streamMessage(msg);
    }
}

function streamMessage(msg) {
    addUserMessage(msg);
    el("#main").classList.add("has-messages");
    el("#brand-area").style.display = "none";
    el("#chat-messages").style.display = "";
    el("#chat-area").style.justifyContent = "flex-start";
    var label = el("#mode-label");
    var modeNames = { agent: "智能问答", volunteer: "志愿评估" };
    var mode = window._currentMode || "agent";
    if (label) label.textContent = modeNames[mode] || mode;
    var skeleton = createAgentSkeleton();
    startThinkingTimer(skeleton);
    var state = window.sidebarState || {};
    var sid = state.currentSessionId;
    streamChat(msg, sid, mode, {
        onThinking: function (j) { updateThinking(skeleton, j.text || ""); },
        onToken: function (j) { appendToken(skeleton, j.text || ""); },
        onDone: function (j) {
            finalizeThinking(skeleton, j.thinking_time);
            // Convert Markdown to formatted HTML
            var respEl = skeleton.querySelector(".response-text");
            if (respEl) {
                respEl.innerHTML = renderMarkdown(respEl.textContent);
                // Collapse reference section after the last <hr>
                collapseReferences(respEl);
            }
            finalizeMessage(skeleton);
            if (j.session_id && j.session_id !== sid && window.sidebarState) {
                window.sidebarState.currentSessionId = j.session_id;
            }
            renderSessionList();
            unlockInput();
        },
        onError: function (e) { showToast("错误: " + e); unlockInput(); }
    });
    scrollToBottom();
}

function collapseReferences(respEl) {
    // Find content after the last <hr> and wrap in collapsible block
    var hrs = respEl.querySelectorAll(".md-hr");
    if (!hrs.length) return;
    var lastHr = hrs[hrs.length - 1];
    // Collect all siblings after the last <hr>
    var nodes = [];
    var next = lastHr.nextSibling;
    while (next) {
        nodes.push(next);
        next = next.nextSibling;
    }
    if (!nodes.length) return;
    // Create wrapper
    var wrapper = document.createElement("div");
    wrapper.className = "ref-block";
    wrapper.innerHTML = '<div class="ref-header"><span class="ref-arrow">&#9654;</span> 参考来源</div><div class="ref-body"></div>';
    var refBody = wrapper.querySelector(".ref-body");
    nodes.forEach(function (n) { refBody.appendChild(n); });
    // Replace: keep the <hr> but append wrapper after it
    lastHr.parentNode.insertBefore(wrapper, lastHr.nextSibling);
    // Toggle
    wrapper.querySelector(".ref-header").addEventListener("click", function () {
        wrapper.classList.toggle("expanded");
    });
}

document.addEventListener("DOMContentLoaded", function () {
    el("#send-btn").addEventListener("click", onSendMessage);
    el("#msg-input").addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSendMessage();
        }
    });
});
