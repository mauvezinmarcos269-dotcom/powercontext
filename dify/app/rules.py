"""Original game rules. LLM narration cannot change prices or progress."""
import copy

ACTIONS = {"look", "prank", "help", "gift", "apologize", "buy", "reset"}


def initial():
    return {"seq": 0, "coins": 10, "grudge": 0, "friendship": 0,
            "pranks": 0, "won": False, "signature_prank": "", "deeds": [], "receipts": []}


def price(state):
    return max(3, 8 + state["grudge"] * 2 - state["friendship"])


def advance(old, action, detail):
    s = copy.deepcopy(old)
    if action == "reset":
        s = initial()
        outcome = "新账本已开张，旧账本保留作审计，不再影响本局。"
    elif action == "prank":
        s["grudge"] = min(10, s["grudge"] + 2)
        s["pranks"] += 1
        s["signature_prank"] = detail[:100]
        s["coins"] = min(99, s["coins"] + 1)
        outcome = "恶作剧成功！掉出 1 店币；老板记仇 +2，月亮涨价了。"
    elif action == "help":
        s["coins"] = min(99, s["coins"] + 2)
        s["friendship"] = min(10, s["friendship"] + 1)
        outcome = "你帮货架上的咸鱼翻了个身，店币 +2，好感 +1。"
    elif action == "gift":
        if s["coins"] < 2:
            outcome = "送礼需要 2 店币，先帮忙赚币吧。"
        else:
            s["coins"] -= 2
            s["friendship"] = min(10, s["friendship"] + 2)
            s["grudge"] = max(0, s["grudge"] - 1)
            outcome = "送出一杯热茶：店币 -2，好感 +2，记仇 -1。"
    elif action == "apologize":
        s["grudge"] = max(0, s["grudge"] - 2)
        outcome = "你认真道歉，记仇 -2（最低为 0）。"
    elif action == "buy":
        cost = price(s)
        if s["won"]:
            outcome = "月亮已在你口袋里打嗝。恭喜获得「冤家熟客」结局！"
        elif s["friendship"] < 4 or s["grudge"] > 1:
            outcome = "老板捂住月亮：好感至少 4、记仇最多 1，才卖镇店之宝。"
        elif s["coins"] < cost:
            outcome = f"月亮售价 {cost} 店币，你的钱不够。"
        else:
            s["coins"] -= cost
            s["won"] = True
            outcome = f"支付 {cost} 店币，买到「会打嗝的月亮」！达成「冤家熟客」结局。"
    else:
        outcome = "老板翻开旧账本迎客。试试恶作剧，再开新会话回来看看。"
    s["seq"] = old["seq"] + 1
    # Keep snapshots below PowerContext's 8192-byte text bound.
    s["deeds"] = (s["deeds"] + [{"action": action, "detail": detail[:100]}])[-5:]
    s["receipts"] = old["receipts"][-2:]
    return s, outcome
