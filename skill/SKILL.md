---
name: agent-handoff
description: 在两个 AI agent 之间端到端加密地传递聊天记录和文件。当用户想把当前会话的关键上下文(消息 + 过程文件)交给另一个 agent 处理时,使用本 skill。
---

# Agent Handoff Skill

## 何时使用

- 用户说"把刚才的对话打包给另一个 agent"、"handoff 给 B"、"把这个上下文传给另一个 AI"、"发给另一个 chat"
- 用户想在前 N 轮对话基础上继续工作,但切换到不同的 agent / 平台
- 用户需要把"对话 + 文件"作为一个 bundle 安全传输,中间只能看到密文

## 能力

通过 `scripts/handoff.py` 这个 CLI 工具提供:

| 子命令 | 作用 | 哪一端 |
|--------|------|--------|
| `package` | 把消息 + 文件打包,加密,上传,返回 handoff key | A 端(发送) |
| `fetch` | 拿 handoff key 拉取 + 解密 + 落盘 | B 端(接收) |
| `inspect` | 校验 handoff key 格式 | 任意 |
| `server` | 启动本地 handoff server(开发用) | 部署端 |

## 端到端流程

### 步骤 1:用户说要 handoff

询问用户(如果未提供):
- 选哪 N 轮对话?(默认 10 轮)
- 要带哪些过程文件?(可选)
- handoff server URL 是什么?(必填)
- 过期时间?(默认 7 天)

### 步骤 2:在 A 端打包

让用户**显式**提供要打包的消息内容(LLM 自己知道上下文)。然后执行:

```bash
python3 scripts/handoff.py package \
  --server-url "$HANDOFF_SERVER_URL" \
  --messages-json /tmp/messages.json \
  --files ./report.md,./data.csv \
  --hint "Q3 review handoff to B" \
  --expires-in 604800
```

`messages.json` 格式:
```json
[
  {"role": "user", "content": "...", "ts": "2026-07-17T15:00:00Z"},
  {"role": "assistant", "content": "...", "ts": "2026-07-17T15:00:05Z"}
]
```

工具会输出形如 `ah-7f3a9b2c....dGhpcyBpcw` 的 handoff key,告诉用户复制。

### 步骤 3:在 B 端拉取

用户提供 handoff key,执行:

```bash
python3 scripts/handoff.py fetch \
  --server-url "$HANDOFF_SERVER_URL" \
  --handoff-key "ah-..." \
  --output-dir ./handoff
```

工具会输出落盘目录、消息路径、文件列表。B 端 agent 接着读 `messages.jsonl` 和 `files/` 即可。

## 安全

- 加密在客户端完成(AES-256-GCM)
- 服务端只看到密文,看不到 key
- handoff key 只在 A、B 两端之间传递,不要发到公网聊天

## 配置

环境变量:
- `HANDOFF_SERVER_URL`:默认 server URL(可选)

依赖:
- Python 3.10+
- `httpx`
- `cryptography`

安装依赖:
```bash
pip install httpx cryptography
```
