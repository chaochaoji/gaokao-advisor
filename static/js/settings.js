// settings.js - 系统设置面板
document.addEventListener("DOMContentLoaded", function () {
    // Open settings modal
    el("#settings-btn").addEventListener("click", function () {
        loadSettings();
        el("#settings-overlay").classList.remove("hidden");
    });

    // Close on X button
    el("#settings-close").addEventListener("click", closeSettings);

    // Close on overlay click
    el("#settings-overlay").addEventListener("click", function (e) {
        if (e.target === el("#settings-overlay")) closeSettings();
    });

    // Close on Escape key
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && !el("#settings-overlay").classList.contains("hidden")) {
            closeSettings();
        }
    });

    // Save config
    el("#settings-form").addEventListener("submit", function (e) {
        e.preventDefault();
        saveCurrentSettings();
    });
});

function closeSettings() {
    el("#settings-overlay").classList.add("hidden");
}

function loadSettings() {
    getConfig().then(function (cfg) {
        setVal("#cfg-primary-key", cfg.llm_primary_api_key || "");
        setVal("#cfg-primary-model", cfg.llm_primary_model || "deepseek-v4-pro");
        setVal("#cfg-fallback-key", cfg.llm_fallback_api_key || "");
        setVal("#cfg-fallback-model", cfg.llm_fallback_model || "deepseek-v4-pro");
    }).catch(function (e) {
        showToast("加载配置失败: " + (e.message || "请检查服务是否运行"));
    });
}

function saveCurrentSettings() {
    var data = {
        llm_primary_api_key: getVal("#cfg-primary-key"),
        llm_primary_model: getVal("#cfg-primary-model") || "deepseek-v4-pro",
        llm_fallback_api_key: getVal("#cfg-fallback-key"),
        llm_fallback_model: getVal("#cfg-fallback-model") || "deepseek-v4-pro",
        gradio_port: 7860
    };

    var btn = el("#cfg-save");
    btn.disabled = true;
    btn.textContent = "保存中...";

    saveConfig(data).then(function () {
        btn.textContent = "已保存 ✓";
        btn.style.background = "#22c55e";
        showToast("配置已保存！请重启服务使配置生效。");
        setTimeout(function () {
            btn.disabled = false;
            btn.textContent = "保存配置";
            btn.style.background = "";
            closeSettings();
        }, 1500);
    }).catch(function (e) {
        showToast("保存失败: " + (e.message || "未知错误"));
        btn.disabled = false;
        btn.textContent = "保存配置";
    });
}

function getVal(sel) {
    var el = document.querySelector(sel);
    return el ? el.value : "";
}

function setVal(sel, val) {
    var el = document.querySelector(sel);
    if (el) el.value = val;
}
