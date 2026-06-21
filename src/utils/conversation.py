"""Per-session context extraction (province, score, category)."""
import re


class SessionContext:
    """Per-session context extraction. Each chat session creates one instance."""

    def __init__(self):
        self.context_state = {
            "province": None, "score": None, "category": None,
            "subject_combo": None, "interests": [], "key_facts": [],
            "last_schools": [], "last_majors": [],
        }

    def update(self, user_msg: str) -> None:
        self._extract_state(user_msg)

    def _extract_state(self, msg):
        PROVINCES = [
            "河南", "河北", "山东", "广东", "四川", "江苏", "浙江",
            "湖北", "湖南", "北京", "上海", "天津", "重庆", "陕西",
            "福建", "安徽", "江西", "山西", "辽宁", "吉林", "黑龙江",
        ]
        for p in PROVINCES:
            if p in msg:
                self.context_state["province"] = p
                break
        score_match = re.search(r"(\d{3})\s*分", msg)
        if score_match:
            self.context_state["score"] = int(score_match.group(1))
        if "理科" in msg or "物理类" in msg:
            self.context_state["category"] = "物理类"
        elif "文科" in msg or "历史类" in msg:
            self.context_state["category"] = "历史类"

    def resolve_references(self, query):
        schools = self.context_state.get("last_schools", [])
        for school in schools:
            for short in [school[:2], school[-3:]]:
                if short in query:
                    query = query.replace(short, school)
        return query

    def get_context(self):
        return {"context_state": self.context_state}
