// sidebar.js
window.sidebarState = { currentSessionId: null, expanded: true };

function initSidebar() {
    el("#collapse-btn").addEventListener("click", toggleSidebar);
    el("#sidebar-new-btn").addEventListener("click", onNewSession);
    el("#search-input").addEventListener("keydown", function (e) {
        if (e.key === "Enter") onSearch(e.target.value);
    });
    el("#session-list").addEventListener("click", function (e) {
        var item = e.target.closest(".session-item");
        if (!item) return;
        if (e.target.closest(".delete-btn")) {
            e.stopPropagation();
            onDeleteSession(item.dataset.sid);
            return;
        }
        selectSession(item.dataset.sid);
    });
    renderSessionList();
}

function renderSessionList() {
    listSessions().then(function (sessions) {
        var html = "";
        sessions.forEach(function (s) {
            var active = s.id === sidebarState.currentSessionId ? " active" : "";
            html += '<div class="session-item' + active + '" data-sid="' + escapeHtml(s.id) + '">';
            html += '<div class="session-item-content"><div class="session-item-title">' + escapeHtml(s.title) + '</div>';
            html += '<div class="session-item-date">' + formatTime(s.updated_at) + '</div></div>';
            html += '<button class="delete-btn" title="删除">X</button></div>';
        });
        if (!sessions.length) html = '<div class="empty-state"><p>暂无对话</p></div>';
        el("#session-list").innerHTML = html;
    }).catch(function (e) {
        console.error("加载会话列表失败:", e);
    });
}

function selectSession(sid) {
    sidebarState.currentSessionId = sid;
    renderSessionList();
    // Clean up ALL areas, then show only chat
    hideAllPanels();
    el("#main").classList.add("has-messages");
    el("#chat-messages").style.display = "";
    el("#chat-area").style.justifyContent = "flex-start";
    el("#input-bar").style.display = "";
    // Reset mode to agent (this is a chat session)
    if (window._currentMode !== "agent") {
        updateModeButtons("agent");
        window._currentMode = "agent";
    }
    var label = el("#mode-label");
    if (label) label.textContent = "智能问答";
    getMessages(sid).then(function (msgs) {
        el("#chat-messages").innerHTML = "";
        if (msgs && msgs.length) renderMessages(msgs);
    }).catch(function (e) {
        console.error("加载消息失败:", e);
    });
}

// Helper: hide all dynamic panels
function hideAllPanels() {
    el("#brand-area").style.display = "none";
    el("#chat-messages").style.display = "none";
    el("#chat-messages").innerHTML = "";
    el("#tool-panel").style.display = "none";
    el("#tool-panel").innerHTML = "";
    el("#main").classList.remove("has-messages");
}

// Helper: update mode button active state without full switchMode
function updateModeButtons(mode) {
    els(".mode-btn").forEach(function (b) {
        b.classList.toggle("active", b.dataset.mode === mode);
        if (b.dataset.mode === mode) {
            b.className = "mode-btn active px-4 py-1.5 text-sm rounded-full font-medium transition-all bg-blue-600 text-white shadow-md shadow-blue-600/20";
        } else {
            b.className = "mode-btn px-4 py-1.5 text-sm rounded-full font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-200/80 transition-all";
        }
    });
}

function onNewSession() {
    createSession().then(function (data) {
        sidebarState.currentSessionId = data.id;
        renderSessionList();
        hideAllPanels();
        el("#brand-area").style.display = "";
        el("#input-bar").style.display = "";
        // Reset mode to agent
        if (window._currentMode !== "agent") {
            updateModeButtons("agent");
            window._currentMode = "agent";
        }
        var label = el("#mode-label");
        if (label) label.textContent = "智能问答";
        el("#msg-input").focus();
    }).catch(function (e) {
        showToast("创建会话失败");
    });
}

function onDeleteSession(sid) {
    if (!confirm("确定删除此对话？")) return;
    deleteSession(sid).then(function () {
        if (sidebarState.currentSessionId === sid) {
            sidebarState.currentSessionId = null;
            hideAllPanels();
            el("#brand-area").style.display = "";
            el("#input-bar").style.display = "";
            if (window._currentMode !== "agent") {
                updateModeButtons("agent");
                window._currentMode = "agent";
            }
            var label = el("#mode-label");
            if (label) label.textContent = "智能问答";
        }
        renderSessionList();
    }).catch(function () {
        showToast("删除失败");
    });
}

function toggleSidebar() {
    sidebarState.expanded = !sidebarState.expanded;
    el("#sidebar").classList.toggle("collapsed", !sidebarState.expanded);
}

function onSearch(query) {
    if (!query || !query.trim()) {
        renderSessionList();
        return;
    }
    searchConversations(query).then(function (data) {
        var html = "";
        (data.results || []).forEach(function (r) {
            html += '<div class="search-result-item" data-sid="' + escapeHtml(r.conversation_id) + '">';
            html += escapeHtml((r.content || "").substring(0, 60)) + '</div>';
        });
        el("#session-list").innerHTML = html || '<div class="empty-state">无结果</div>';
    });
}
