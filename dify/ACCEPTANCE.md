# 实际验收记录

2026-10-30，在本机 Windows、Docker Desktop Linux containers、Python 3.13 环境执行。以下均为真实服务运行结果，未使用假的 PowerContext 或假的模型响应。

| 验收内容 | 结果 | 证据 |
| --- | --- | --- |
| Dify 1.9.1 导入 DSL 0.4.0 并发布 | `completed`，9 节点，无外部插件依赖 | `evidence/dify-import.json` |
| 完整 Dify 玩法 | 16 项检查通过；8 次互动 × 9 节点 = 72 个成功节点 | `evidence/dify-run.json` |
| 跨会话记忆 | 新 conversation、同一 API user；旧 Artifact 进入下一次读记忆，模型提及具体恶作剧 | `evidence/dify-run.json` 第 1、2 轮 |
| 游戏闭环 | 恶作剧 → 帮忙 → 送礼两次 → 买到月亮；6 店币、记仇 0、好感 5 | `evidence/dify-run.json` 第 6 轮 |
| 不同玩家隔离 | 新 API user 初始 10 店币，不读取前一玩家旧账 | `evidence/dify-run.json` 第 7 轮 |
| 重置可复现 | 原玩家重开恢复初始数值，以新快照覆盖当前状态 | `evidence/dify-run.json` 第 8 轮 |
| 后端联调 | 9 项检查通过：真实存取、模型引用旧事、身份隔离、幂等、篡改检查 | `evidence/bridge-run.json` |
| PowerContext 故障与恢复 | 停止本次 PC 进程后读取返回 503；用同一目录重启后，状态和 Artifact ID 完全相同 | `evidence/restart-and-outage.json` |
| 实际 WebApp 游玩 | 本机 Chrome 中点击建议问题，工作流成功，显示第 1 笔账已保存 | `evidence/webapp-render.json`、两张 PNG |

![真实 WebApp 游玩截图](evidence/webapp-play.png)

## 如何核对指定技术的实际作用

1. 打开 `dify-run.json`，第一轮末尾的「PowerContext 写入」ID 是真实 `art_...`。
2. 第二轮 `conversation_id` 与第一轮不同；第二轮末尾「本轮读取」ID 等于第一轮写入 ID。
3. 第二轮 `answer` 提到尖叫鸡／招财猫；它来自旧账，不来自 Dify 的同一会话历史。
4. 每轮节点轨迹包含 `recall`、`model`、`save`，均为实际 Dify HTTP 节点。
5. `bridge-run.json` 同时保留后端读取的原始业务状态、模型名 `MiniMax-M2.5`、usage 和实际写入回执，便于交叉核对。

## 复跑

按 README 启动三组服务，运行 `samples/verify_bridge.py` 和 `samples/verify_dify.py`。每次使用独立随机玩家；它们会更新对应证据文件。若要复跑停机验证，依次运行 `verify_restart.py --phase before`、停止本作品的 PowerContext、`--phase outage`、以原数据目录启动 PowerContext、`--phase after`。

截图辅助使用本机 Chrome 和已经安装的 WebSocket 运行库，不属于应用启动依赖。日志已去除请求头、模型密钥、管理员密码、签名票据等凭据；公开的玩家 ID 是随机测试标识。

本题说明未公布具体评分细则和自动评分工作流，当前比赛基线只包含赛题目录占位文件。本记录证明本地验收结果，不宣称赛事满分或 GitHub Actions 跑分通过。
