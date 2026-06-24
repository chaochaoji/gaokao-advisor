// app.js - 应用编排
window._currentMode = "agent";

function calcProbability(userRank, schoolMinRank) {
    if (!userRank || !schoolMinRank || schoolMinRank <= 0) return 0.5;
    var ratio = userRank / schoolMinRank;
    if (ratio >= 1.05) return Math.min(0.95, 0.6 + (ratio - 1.05) * 2);
    if (ratio >= 0.95) return 0.5 + (ratio - 0.95) * 5;
    return Math.max(0.1, 0.3 - (0.95 - ratio) * 2);
}

function probClass(p) {
    return p >= 0.8 ? 'high' : p >= 0.5 ? 'mid' : 'low';
}

function tierBadgeClass(tier) {
    if (tier === '冲刺') return 'badge-tier-chongci';
    if (tier === '稳妥') return 'badge-tier-wentuo';
    if (tier === '保底') return 'badge-tier-baodi';
    return 'badge-tier-wentuo';
}

function typeBadgeClass(type) {
    if (type && type.indexOf('985') !== -1) return 'badge-985';
    if (type && type.indexOf('211') !== -1) return 'badge-211';
    return '';
}

function init() {
    initSidebar();
    els(".mode-btn").forEach(function (btn) {
        btn.addEventListener("click", function () { switchMode(this.dataset.mode); });
    });
}

function switchMode(mode) {
    window._currentMode = mode;
    updateModeButtons(mode);
    hideAllPanels();

    var label = el("#mode-label");
    var modeNames = { agent: "智能问答", volunteer: "志愿评估" };
    if (label) label.textContent = modeNames[mode] || mode;

    if (mode === "agent") {
        el("#brand-area").style.display = "";
        el("#input-bar").style.display = "";
    } else if (mode === "volunteer") {
        el("#main").classList.add("has-messages");
        el("#tool-panel").style.display = "";
        el("#input-bar").style.display = "none";
        renderVolunteerForm();
    }
}

function renderVolunteerForm() {
    el("#tool-panel").innerHTML = '<h3>志愿评估</h3>'
        + '<div class="form-group"><label>考生省份</label><select id="v-province" class="pill-input">'
        + '<option value="北京">北京</option><option value="天津">天津</option>'
        + '<option value="河北">河北</option><option value="山西">山西</option>'
        + '<option value="内蒙古">内蒙古</option><option value="辽宁">辽宁</option>'
        + '<option value="吉林">吉林</option><option value="黑龙江">黑龙江</option>'
        + '<option value="上海">上海</option><option value="江苏">江苏</option>'
        + '<option value="浙江">浙江</option><option value="安徽">安徽</option>'
        + '<option value="福建">福建</option><option value="江西">江西</option>'
        + '<option value="山东">山东</option><option value="河南">河南</option>'
        + '<option value="湖北">湖北</option><option value="湖南">湖南</option>'
        + '<option value="广东">广东</option><option value="广西">广西</option>'
        + '<option value="海南">海南</option><option value="重庆">重庆</option>'
        + '<option value="四川">四川</option><option value="贵州">贵州</option>'
        + '<option value="云南">云南</option><option value="西藏">西藏</option>'
        + '<option value="陕西">陕西</option><option value="甘肃">甘肃</option>'
        + '<option value="青海">青海</option><option value="宁夏">宁夏</option>'
        + '<option value="新疆">新疆</option>'
        + '</select></div>'
        + '<div class="form-group"><label>分数</label><input id="v-score" class="pill-input" type="number" value="600" min="0" max="750"></div>'
        + '<div class="form-group"><label>位次（选填）</label><input id="v-rank" class="pill-input" type="number" placeholder="如：12000" min="0"></div>'
        + '<div class="form-group"><label>科类</label><div class="radio-group">'
        + '<label><input type="radio" name="v-cat" value="物理类" checked><span>物理类</span></label>'
        + '<label><input type="radio" name="v-cat" value="历史类"><span>历史类</span></label>'
        + '</div></div>'
        + '<div class="form-group"><label>意向专业</label><textarea id="v-interests" class="pill-textarea" placeholder="如：计算机、人工智能、医学"></textarea></div>'
        + '<div class="form-group"><label>期望省份/城市（选填）</label><input id="v-desired-location" class="pill-input" type="text" placeholder="如：北京、江浙沪、不限制"></div>'
        + '<button class="form-submit-btn" id="v-submit">提交评估</button>'
        + '<div id="v-result" class="tool-result" style="display:none"></div>';
    el("#v-submit").addEventListener("click", handleVolunteerSubmit);
}

function renderVolunteerResult(data) {
    var summary = data.summary || {};
    var schools = data.schools || [];
    var majorAnalysis = data.major_analysis || {};
    var risks = data.risks || [];
    var sources = data.data_sources || [];
    var dataYear = data.data_year || '';
    var userRank = summary.rank || 0;

    var html = '<div class="assessment-result">';

    // --- 位次定位摘要 ---
    html += '<div class="position-card">';
    html += '<div class="pos-score">' + escapeHtml(String(summary.score || '--')) + '分</div>';
    html += '<div class="pos-rank">位次约 ' + escapeHtml(summary.position || '估算中') + '</div>';
    html += '<div class="pos-advice">' + escapeHtml(summary.advice || '') + '</div>';
    html += '</div>';

    // --- Tier 筛选 tabs ---
    html += '<div class="tier-tabs">';
    html += '<button class="tier-tab active" data-filter="all">全部 (' + schools.length + ')</button>';
    var tiers = ['冲刺', '稳妥', '保底'];
    tiers.forEach(function(t) {
        var count = schools.filter(function(s) { return s.tier === t; }).length;
        html += '<button class="tier-tab" data-filter="' + t + '">' + t + ' (' + count + ')</button>';
    });
    html += '</div>';

    // --- 院校列表 ---
    html += '<div id="school-list">';
    schools.forEach(function(s) {
        var prob = calcProbability(userRank, s.min_rank);
        var pc = probClass(prob);
        html += renderSchoolCard(s, prob, pc);
    });
    html += '</div>';

    // --- 专业与就业分析 ---
    if (majorAnalysis.summary || (majorAnalysis.pros || []).length > 0) {
        html += '<div class="analysis-section">';
        html += '<h4>📊 专业与就业分析</h4>';
        if (majorAnalysis.summary) {
            html += '<p style="font-size:.8125rem;color:#475569;margin-bottom:.5rem">' + escapeHtml(majorAnalysis.summary) + '</p>';
        }
        html += '<div class="analysis-pros-cons">';
        if ((majorAnalysis.pros || []).length > 0) {
            html += '<div class="analysis-pros"><strong style="color:#16a34a">✅ 优势</strong><ul>';
            majorAnalysis.pros.forEach(function(p) { html += '<li>' + escapeHtml(p) + '</li>'; });
            html += '</ul></div>';
        }
        if ((majorAnalysis.cons || []).length > 0) {
            html += '<div class="analysis-cons"><strong style="color:#f59e0b">⚠️ 劣势</strong><ul>';
            majorAnalysis.cons.forEach(function(c) { html += '<li>' + escapeHtml(c) + '</li>'; });
            html += '</ul></div>';
        }
        html += '</div>';
        if (majorAnalysis.grad_school_rate) {
            html += '<p style="font-size:.75rem;color:#94a3b8;margin-top:.5rem">深造比例：' + escapeHtml(majorAnalysis.grad_school_rate) + '</p>';
        }
        html += '</div>';
    }

    // --- 风险提示 ---
    if (risks.length > 0) {
        html += '<div class="risk-section">';
        html += '<h4>⚠️ 风险提示</h4><ul>';
        risks.forEach(function(r) { html += '<li>' + escapeHtml(r) + '</li>'; });
        html += '</ul></div>';
    }

    // --- 数据来源 ---
    if (sources.length > 0 || dataYear) {
        html += '<div class="sources-footer">📎 数据年份：' + escapeHtml(dataYear || '未标注');
        if (sources.length > 0) {
            html += ' · 来源：' + escapeHtml(sources.join('、'));
        }
        html += '</div>';
    }

    html += '</div>'; // .assessment-result

    el("#tool-panel").innerHTML = html;

    // 绑定 tier 筛选
    els("#tool-panel .tier-tab").forEach(function(tab) {
        tab.addEventListener("click", function() {
            els("#tool-panel .tier-tab").forEach(function(t) { t.classList.remove("active"); });
            tab.classList.add("active");
            var filter = tab.dataset.filter;
            els("#school-list .school-card").forEach(function(card) {
                if (filter === 'all' || card.dataset.tier === filter) {
                    card.style.display = '';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });
}

function renderSchoolCard(s, prob, probClass) {
    var badgeClass = typeBadgeClass(s.type);
    var tierClass = tierBadgeClass(s.tier);
    var probPct = Math.round(prob * 100);

    var html = '<div class="school-card" data-tier="' + escapeHtml(s.tier) + '">';

    // Header: 名称 + badges
    html += '<div class="school-card-header">';
    html += '<span class="school-card-name">🏫 ' + escapeHtml(s.name) + '</span>';
    if (s.type) html += '<span class="school-card-badge ' + badgeClass + '">' + escapeHtml(s.type) + '</span>';
    html += '<span class="school-card-badge ' + tierClass + '">' + escapeHtml(s.tier) + '</span>';
    (s.tags || []).forEach(function(t) {
        html += '<span class="school-card-badge badge-tag">' + escapeHtml(t) + '</span>';
    });
    html += '</div>';

    // 城市
    if (s.city) {
        html += '<div style="font-size:.75rem;color:#94a3b8;margin-bottom:.375rem">📍 ' + escapeHtml(s.city) + '</div>';
    }

    // 推荐专业
    if ((s.majors || []).length > 0) {
        html += '<div class="school-card-majors">';
        s.majors.forEach(function(m) { html += '<span>' + escapeHtml(m) + '</span>'; });
        html += '</div>';
    }

    // 最低分/位次
    html += '<div class="school-card-score">';
    html += '最低录取：' + (s.min_score || '--') + '分 / ' + (s.min_rank || '--') + '名';
    html += '</div>';

    // 概率条
    html += '<div class="probability-bar-wrap">';
    html += '<div class="probability-bar"><div class="probability-bar-fill ' + probClass + '" style="width:' + probPct + '%"></div></div>';
    html += '<span class="probability-label" style="color:' + (probPct >= 80 ? '#16a34a' : probPct >= 50 ? '#2563eb' : '#d97706') + '">' + probPct + '%</span>';
    html += '</div>';

    // 推荐理由
    if (s.reason) {
        html += '<div class="school-card-reason">💡 ' + escapeHtml(s.reason) + '</div>';
    }

    // 风险提示
    if (s.risk_note) {
        html += '<div class="school-card-risk">⚠️ ' + escapeHtml(s.risk_note) + '</div>';
    }

    html += '</div>';
    return html;
}

function handleVolunteerSubmit() {
    var data = {
        province: el("#v-province").value,
        score: parseInt(el("#v-score").value) || 600,
        rank: parseInt(el("#v-rank").value) || 0,
        category: (els('input[name="v-cat"]:checked')[0] || {}).value || "物理类",
        interests: el("#v-interests").value || "",
        desired_location: el("#v-desired-location").value || ""
    };
    var btn = el("#v-submit");
    data.session_id = window._currentSid || sidebarState.currentSessionId || "";
    btn.disabled = true; btn.textContent = "处理中...";
    volunteerTool(data).then(function (res) {
        btn.disabled = false; btn.textContent = "提交评估";
        if (res.parse_error && res.fallback_text) {
            // 解析失败，显示纯文本
            el("#v-result").style.display = "";
            el("#v-result").innerHTML = '<h4>评估结果（文本模式）</h4><div class="result-text">'
                + renderMarkdown(res.fallback_text) + '</div>';
        } else if (res.structured_data) {
            // 结构化渲染 — renderVolunteerResult 渲染到 #tool-panel
            el("#tool-panel").innerHTML = '';
            renderVolunteerResult(res.structured_data);
        }
        if (res.session_id) {
            window._currentSid = res.session_id;
            window.sidebarState.currentSessionId = res.session_id;
            if (typeof renderSessionList === "function") renderSessionList();
        }
    }).catch(function (e) {
        showToast("错误: " + e.message);
        btn.disabled = false; btn.textContent = "提交评估";
    });
}

document.addEventListener("DOMContentLoaded", function () { init(); });
