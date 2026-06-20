import json
from pathlib import Path


class HealthManager:
    @staticmethod
    def get_report(log_dir="logs"):
        hp = Path(log_dir) / "health.json"
        if not hp.exists():
            return "暂无健康数据"
        health = json.loads(hp.read_text(encoding="utf-8"))
        lines = [f"=== 服务健康报告 ({health.get('updated_at','N/A')}) ===", ""]
        icons = {"healthy": "🟢", "degraded": "🟠", "unhealthy": "🔴"}
        for svc, info in health.get("services", {}).items():
            icon = icons.get(info.get("status", ""), "⚪")
            lines.append(f"{icon} {svc}: {info.get('status','unknown')}")
            if info.get("last_error"):
                lines.append(f"   上次错误: {info['last_error']}")
        errors = health.get("recent_errors", [])
        if errors:
            lines.append("")
            lines.append("--- 最近错误 ---")
            for err in errors[:5]:
                lines.append(f"  [{err.get('time','?')}] {err.get('component','?')}: {err.get('error','?')[:100]}")
                lines.append(f"   处理: {err.get('action_taken','?')}")
                lines.append(f"   建议: {err.get('fix_suggestion','?')}")
        return "\n".join(lines)
