import re


class ConversationManager:
    def __init__(self, max_window=3, max_history=10):
        self.messages = []
        self.max_window = max_window
        self.max_history = max_history
        self.context_state = {
            "province": None, "score": None, "category": None,
            "subject_combo": None, "interests": [], "key_facts": [],
            "last_schools": [], "last_majors": [],
        }

    def add_turn(self, user_msg, agent_msg):
        self.messages.append({"role": "user", "content": user_msg})
        self.messages.append({"role": "assistant", "content": agent_msg})
        self._extract_state(user_msg)

    def _extract_state(self, msg):
        # 省份提取 (简化版，实际使用 NER 模型或 LLM)
        PROVINCES = [
            "河南", "河北", "山东", "广东", "四川", "江苏", "浙江",
            "湖北", "湖南", "北京", "上海", "天津", "重庆", "陕西",
            "福建", "安徽", "江西", "山西", "辽宁", "吉林", "黑龙江",
        ]
        for p in PROVINCES:
            if p in msg:
                self.context_state["province"] = p
                break

        # 分数提取
        score_match = re.search(r"(\d{3})\s*分", msg)
        if score_match:
            self.context_state["score"] = int(score_match.group(1))

        # 科类提取
        if "理科" in msg or "物理类" in msg:
            self.context_state["category"] = "物理类"
        elif "文科" in msg or "历史类" in msg:
            self.context_state["category"] = "历史类"

    def get_recent_messages(self, n=None):
        if n is None:
            n = self.max_window
        return self.messages[-n * 2:]

    def resolve_references(self, query):
        schools = self.context_state.get("last_schools", [])
        for school in schools:
            for short in [school[:2], school[-3:]]:
                if short in query:
                    query = query.replace(short, school)
        return query

    def get_context(self):
        return {
            "context_state": self.context_state,
            "recent_messages": self.get_recent_messages(),
        }
