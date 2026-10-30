"""Build the deliverable DSL without any credentials or provider plugins."""
from pathlib import Path
import textwrap
import yaml

ROOT = Path(__file__).resolve().parents[1]


def code_node(node_id, title, code, variables, outputs, x):
    return {"id": node_id, "type": "custom", "position": {"x": x, "y": 260},
        "width": 244, "height": 98, "sourcePosition": "right", "targetPosition": "left",
        "data": {"type": "code", "title": title, "desc": "", "selected": False,
            "code_language": "python3", "code": textwrap.dedent(code).strip(),
            "variables": [{"variable": name, "value_selector": selector} for name, selector in variables],
            "outputs": {name: {"type": typ, "children": None} for name, typ in outputs.items()}}}


def http_node(node_id, title, route, body_selector, x):
    return {"id": node_id, "type": "custom", "position": {"x": x, "y": 260},
        "width": 244, "height": 122, "sourcePosition": "right", "targetPosition": "left",
        "data": {"type": "http-request", "title": title, "desc": "", "selected": False,
            "method": "post", "url": "{{#env.SHOP_BASE_URL#}}" + route,
            "authorization": {"type": "no-auth"},
            "headers": "Content-Type:application/json\nAuthorization:Bearer {{#env.SHOP_API_KEY#}}",
            "params": "", "body": {"type": "json", "data": [{"key": "", "type": "text", "value": "{{#" + body_selector + "#}}"}]},
            "timeout": {"connect": 10, "read": 180, "write": 20}, "ssl_verify": True,
            "retry_config": {"retry_enabled": False, "max_retries": 0, "retry_interval": 1000}}}


def build():
    nodes = [{"id": "start", "type": "custom", "position": {"x": 0, "y": 260}, "width": 244, "height": 54,
        "sourcePosition": "right", "targetPosition": "left",
        "data": {"type": "start", "title": "进店", "desc": "同一浏览器或 API user 对应同一账本", "variables": [], "selected": False}}]
    nodes.append(code_node("input", "识别动作 · 安全编码", '''
        import json
        def main(query: str, user: str, run: str, app: str) -> dict:
            query = query.strip()
            if not query or len(query) > 400:
                raise ValueError("请输入 1～400 字的动作")
            action = "look"
            commands = {"恶作剧": "prank", "帮忙": "help", "送礼": "gift", "道歉": "apologize", "买月亮": "buy", "重开": "reset", "看看": "look"}
            for prefix, value in commands.items():
                if query == prefix or query.startswith(prefix + " ") or query.startswith(prefix + "：") or query.startswith(prefix + ":"):
                    action = value
                    break
            return {"body": json.dumps({"player": "dify:" + app + ":" + user,
                "operation_id": run, "action": action, "detail": query}, ensure_ascii=False)}
    ''', [("query", ["sys", "query"]), ("user", ["sys", "user_id"]), ("run", ["sys", "workflow_run_id"]), ("app", ["sys", "app_id"])], {"body": "string"}, 300))
    nodes.append(http_node("recall", "PowerContext · 读取旧账", "/turn/prepare", "input.body", 600))
    nodes.append(code_node("ticket", "核对记忆读取结果", '''
        import json
        def main(body: str, status: int) -> dict:
            if status != 200:
                raise ValueError("旧账读取失败，本轮未继续；请检查记忆服务后重试")
            data = json.loads(body)
            return {"body": json.dumps({"ticket": data["ticket"]}), "ticket": data["ticket"]}
    ''', [("body", ["recall", "body"]), ("status", ["recall", "status_code"])], {"body": "string", "ticket": "string"}, 900))
    nodes.append(http_node("model", "MiniMax · 老板即兴接梗", "/turn/narrate", "ticket.body", 1200))
    nodes.append(code_node("narration", "核对模型结果 · 准备存档", '''
        import json
        def main(body: str, status: int, ticket: str) -> dict:
            if status != 200:
                raise ValueError("老板暂时卡壳，本轮尚未存档；请稍后重试")
            data = json.loads(body)
            return {"body": json.dumps({"ticket": ticket, "narration": data["narration"],
                "narration_proof": data["narration_proof"]}, ensure_ascii=False)}
    ''', [("body", ["model", "body"]), ("status", ["model", "status_code"]), ("ticket", ["ticket", "ticket"])], {"body": "string"}, 1500))
    nodes.append(http_node("save", "PowerContext · 写入新账", "/turn/commit", "narration.body", 1800))
    nodes.append(code_node("display", "展示结果 · 存档凭证", r'''
        import json
        def main(body: str, status: int) -> dict:
            if status != 200:
                raise ValueError("本轮存档未确认（可能有并发或服务故障），请重新进店查看账本")
            r = json.loads(body)
            s = r["state"]
            medal = " · 🌙 冤家熟客结局已解锁" if s["won"] else ""
            recalled = "旧账已召回" if r["recalled_memory_id"] else "首次进店"
            text = f"### 🏮 葛掌柜\n\n{r['narration']}\n\n**本轮结果**：{r['outcome']}\n\n🪙 {s['coins']} 店币 · 🌶️ 记仇 {s['grudge']}/10 · 🍵 好感 {s['friendship']}/10{medal}\n\n🌙 月亮现价 **{r['moon_price']}** 店币（好感 ≥4、记仇 ≤1 才能买）\n\n---\n输入：`恶作剧 你的点子` · `帮忙` · `送礼` · `道歉` · `买月亮` · `看看` · `重开`\n\n💾 第 {s['seq']} 笔账已保存 · {recalled}\n\n<details><summary>记忆存档凭证</summary>\n\nPowerContext 写入：`{r['memory_id']}`\n\n本轮读取：`{r['recalled_memory_id'] or '无'}`\n\n</details>"
            return {"answer": text}
    ''', [("body", ["save", "body"]), ("status", ["save", "status_code"])], {"answer": "string"}, 2100))
    nodes.append({"id": "answer", "type": "custom", "position": {"x": 2400, "y": 260}, "width": 244, "height": 105,
        "sourcePosition": "right", "targetPosition": "left", "data": {"type": "answer", "title": "开门迎客", "desc": "",
            "answer": "{{#display.answer#}}", "variables": [], "selected": False}})
    edges = []
    for left, right in zip(nodes, nodes[1:]):
        edges.append({"id": left["id"] + "-" + right["id"], "type": "custom", "source": left["id"], "target": right["id"],
            "sourceHandle": "source", "targetHandle": "target", "data": {"sourceType": left["data"]["type"], "targetType": right["data"]["type"], "isInIteration": False}})
    return {"kind": "app", "version": "0.4.0", "dependencies": [],
        "app": {"name": "记仇杂货铺", "description": "跨会话记得恶作剧的葛掌柜。帮忙、送礼、和解，买走会打嗝的月亮。Dify × PowerContext。",
            "mode": "advanced-chat", "icon": "🏮", "icon_background": "#FFEAD5", "use_icon_as_answer_icon": True},
        "workflow": {"conversation_variables": [],
            "environment_variables": [
                {"id": "f32cf702-0b40-4cd8-8581-95a687a1d041", "name": "SHOP_BASE_URL", "value": "http://host.docker.internal:8012", "value_type": "string", "selector": ["env", "SHOP_BASE_URL"], "description": "Dify 容器可访问的杂货铺服务地址"},
                {"id": "9b9e9e94-7a86-4e1b-b329-4821c5c99903", "name": "SHOP_API_KEY", "value": "REPLACE_WITH_LOCAL_SHOP_API_KEY", "value_type": "secret", "selector": ["env", "SHOP_API_KEY"], "description": "与后端 .env 的 SHOP_API_KEY 一致"}],
            "features": {"opening_statement": "🏮 欢迎来到记仇杂货铺。葛掌柜嘴硬心软，唯一的毛病是：记性太好。\n\n输入「恶作剧 把招财猫换成尖叫鸡」试试，再开一个新会话回来。\n\n目标：让老板愿意卖给你「会打嗝的月亮」。帮忙赚币，送礼增好感，道歉消旧怨。输入「重开」恢复本局初始状态。",
                "suggested_questions": ["恶作剧 把招财猫换成尖叫鸡", "帮忙", "看看"],
                "suggested_questions_after_answer": {"enabled": False}, "retriever_resource": {"enabled": False},
                "speech_to_text": {"enabled": False}, "text_to_speech": {"enabled": False}, "sensitive_word_avoidance": {"enabled": False},
                "file_upload": {"enabled": False}},
            "graph": {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.65}}}}


if __name__ == "__main__":
    path = ROOT / "dsl/grudge-shop.yml"
    path.write_text(yaml.safe_dump(build(), allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    print(path)
