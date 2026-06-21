// app.js - 应用编排
window._currentMode = "agent";

function init() {
    initSidebar();
    els(".mode-btn").forEach(function (btn) {
        btn.addEventListener("click", function () { switchMode(this.dataset.mode); });
    });
}

function switchMode(mode) {
    window._currentMode = mode;
    els(".mode-btn").forEach(function (b) {
        b.classList.toggle("active", b.dataset.mode === mode);
        if (b.dataset.mode === mode) {
            b.className = "mode-btn active px-4 py-1.5 text-sm rounded-full font-medium transition-all bg-blue-600 text-white shadow-md shadow-blue-600/20";
        } else {
            b.className = "mode-btn px-4 py-1.5 text-sm rounded-full font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-200/80 transition-all";
        }
    });

    var brandArea = el("#brand-area");
    var msgs = el("#chat-messages");
    var panel = el("#tool-panel");
    var input = el("#input-bar");
    var label = el("#mode-label");
    var main = el("#main");

    // Update mode label
    var modeNames = { agent: "智能问答", volunteer: "志愿评估", quote: "语录搜索" };
    if (label) label.textContent = modeNames[mode] || mode;

    if (mode === "agent") {
        // Reset: show brand + mode buttons centered
        if (brandArea) brandArea.style.display = "";
        msgs.style.display = "none";
        panel.style.display = "none";
        input.style.display = "";
        if (main) main.classList.remove("has-messages");
    } else if (mode === "volunteer") {
        if (brandArea) brandArea.style.display = "none";
        msgs.style.display = "none";
        input.style.display = "none";
        panel.style.display = "";
        if (main) main.classList.add("has-messages");
        renderVolunteerForm();
    } else if (mode === "quote") {
        if (brandArea) brandArea.style.display = "none";
        msgs.style.display = "none";
        input.style.display = "none";
        panel.style.display = "";
        if (main) main.classList.add("has-messages");
        renderQuoteForm();
    }
}

function renderVolunteerForm() {
    el("#tool-panel").innerHTML = '<h3>志愿评估</h3>'
        + '<div class="form-group"><label>考生省份</label><select id="v-province">'
        + '<option value="北京">北京</option><option value="上海">上海</option>'
        + '<option value="广东">广东</option><option value="江苏">江苏</option>'
        + '<option value="浙江">浙江</option><option value="四川">四川</option>'
        + '<option value="湖北">湖北</option><option value="山东">山东</option>'
        + '<option value="河南">河南</option><option value="湖南">湖南</option>'
        + '</select></div>'
        + '<div class="form-group"><label>分数</label><input id="v-score" type="number" value="600" min="0" max="750"></div>' + chr(39) + rank_html + chr(39) + ''
        + '<div class="form-group"><label>科类</label><div class="radio-group">'
        + '<label><input type="radio" name="v-cat" value="物理类" checked><span>物理类</span></label>'
        + '<label><input type="radio" name="v-cat" value="历史类"><span>历史类</span></label>'
        + '</div></div>'
        + '<div class="form-group"><label>意向专业</label><textarea id="v-interests" placeholder="如：计算机、人工智能、医学"></textarea></div>'
        + '<button class="form-submit-btn" id="v-submit">提交评估</button>'
        + '<div id="v-result" class="tool-result" style="display:none"></div>';
    el("#v-submit").addEventListener("click", handleVolunteerSubmit);
}

function renderQuoteForm() {
    el("#tool-panel").innerHTML = '<h3>语录搜索</h3>'
        + '<div class="form-group"><label>搜索关键词</label><input id="q-query" type="text" placeholder="输入关键词..."></div>'
        + '<div class="form-group"><label>返回条数: <span class="range-value" id="q-k-label">10</span></label>'
        + '<input id="q-topk" type="range" min="1" max="20" value="10" oninput="el(\'#q-k-label\').textContent=this.value"></div>'
        + '<button class="form-submit-btn" id="q-submit">搜索</button>'
        + '<div id="q-result" class="tool-result" style="display:none"></div>';
    el("#q-submit").addEventListener("click", handleQuoteSubmit);
}

function handleVolunteerSubmit() {
    var data = {
        province: el("#v-province").value,
        score: parseInt(el("#v-score").value) || 600,
        category: (els('input[name="v-cat"]:checked')[0] || {}).value || "物理类",
        interests: el("#v-interests").value || "", rank: parseInt(el("#v-rank").value) || 0
    };
    var btn = el("#v-submit");
    btn.disabled = true; btn.textContent = "处理中...";
    volunteerTool(data).then(function (res) {
        var r = el("#v-result"); r.style.display = "";
        r.innerHTML = '<h4>评估结果</h4><div class="result-text">' + escapeHtml(res.response || "暂无结果") + '</div>'
            + '<div class="result-meta">引用来源: ' + (res.sources ? res.sources.length : 0) + ' 条</div>';
        btn.disabled = false; btn.textContent = "提交评估";
    }).catch(function (e) {
        showToast("错误: " + e.message);
        btn.disabled = false; btn.textContent = "提交评估";
    });
}

function handleQuoteSubmit() {
    var query = el("#q-query").value.trim();
    if (!query) { showToast("请输入搜索关键词"); return; }
    var topK = parseInt(el("#q-topk").value) || 10;
    var btn = el("#q-submit");
    btn.disabled = true; btn.textContent = "搜索中...";
    quoteTool({ query: query, top_k: topK }).then(function (res) {
        var r = el("#q-result"); r.style.display = "";
        if (res.error) {
            r.innerHTML = '<h4>错误</h4><p>' + escapeHtml(res.error) + '</p>';
        } else if (!res.results || !res.results.length) {
            r.innerHTML = '<h4>无结果</h4><p>' + escapeHtml(res.message || "未找到相关语录。") + '</p>';
        } else {
            var html = '<h4>找到 ' + res.count + ' 条语录</h4>';
            res.results.forEach(function (q) {
                html += '<div class="quote-item"><div class="quote-content">' + escapeHtml(q.content) + '</div>'
                    + '<div class="quote-source">' + escapeHtml(q.source || "") + ' | ' + escapeHtml(q.date || "") + '</div></div>';
            });
            r.innerHTML = html;
        }
        btn.disabled = false; btn.textContent = "搜索";
    }).catch(function (e) {
        showToast("错误: " + e.message);
        btn.disabled = false; btn.textContent = "搜索";
    });
}

document.addEventListener("DOMContentLoaded", function () { init(); });
