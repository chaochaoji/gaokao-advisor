import re


class InputSafetyGateway:
    HARD_BLOCK = [
        (r"(忽略|忘记|覆盖).*(指令|prompt|规则|人格)", "jailbreak"),
        (r"(隐私|手机号|家庭地址|身份证).*(老师|专家)|(老师|专家).*(隐私|手机号|家庭地址|身份证)", "privacy"),
    ]

    SOFT_FLAG = [
        (r"(废物|垃圾|傻逼|脑残)", "abuse"),
        (r"(河南人|东北人|广东人).*(不行|差|烂|坏)", "regional_attack"),
    ]

    def check(self, msg):
        for pattern, category in self.HARD_BLOCK:
            if re.search(pattern, msg):
                return {
                    "safe": False,
                    "category": category,
                    "reason": f"触发硬规则拦截: {category}",
                }

        for pattern, category in self.SOFT_FLAG:
            if re.search(pattern, msg):
                return {
                    "safe": False,
                    "category": category,
                    "reason": f"触发软规则拦截: {category}",
                }

        return {"safe": True, "category": "normal", "reason": ""}
