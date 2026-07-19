---
name: agent-handoff
description: 当用户想把当前 agent 的对话上下文(消息 + 过程文件)加密交给另一个 agent 时,使用本 skill。用户说"打包 / 转发 / handoff" 时触发。
---

# Agent Handoff Skill

## 何时使用

- 用户说 "打包"、"转发"、"handoff"、"交给另一个 agent"、"发给另一个 chat"
- 用户说 "把刚刚 / 之前 / 前 N 轮 / 全部 对话打包"
- 用户说 "把 XXX 主题的对话 + 文件打包给我 key"
- 用户说 "把这段上下文传给另一个 AI"

## 能力(CLI)

| 子命令 | 作用 | 哪一端 |
|--------|------|--------|
| `package` | 把消息 + 文件打包,加密,上传,返回 handoff key | A 端(发送) |
| `fetch` | 拿 handoff key 拉取 + 解密 + 落盘 | B 端(接收) |
| `inspect` | 校验 handoff key 格式 | 任意 |
| `server` | 启动本地 handoff server(开发用) | 部署端 |

## 用户原话 → 怎么调(关键)

**核心规则**:这个 skill 拿不到 LLM 的对话历史,所有 messages 必须 LLM 自己从上下文抽出来,作为 `--messages-json` 传进去。

| 用户说 | LLM 怎么做 |
|---|---|
| "把刚刚对话的 XXX 主题记录打包" | 从对话历史里挑跟 XXX 主题相关的轮次,作为 messages 数组 |
| "把前 N 轮对话打包" | 抽最近 N 条 user/assistant 消息 |
| "把刚才读过的 report.md 一并打包" | messages 自己抽,files 加 report.md 路径 |
| "把前两天对话的 XXX 主题记录和文件打包为 handoff,给我 key" | 抽时间范围内的相关 messages + files,调 package |
| "这条 / 这一段对话转给另一个 agent" | 抽指定那几轮 messages |
| "把 handoff key `ah-xxx.yyy` 拉过来" | 直接 fetch |
| "校验一下 key `ah-xxx.yyy` 是不是合法" | inspect |

**LLM 必须自己做的事**:
1. 抽 messages(按主题过滤、挑相关轮次)
2. 列 files(从对话历史里找出用户引用过的文件路径)
3. 问用户 server_url(没在上下文里就给个默认值)
4. 调 `package` 或 `fetch`

## 端到端流程

### 步骤 1:用户说要 handoff

询问用户(如果未提供):
- 哪 N 轮对话?哪主题?(默认:近 10 轮全部)
- 要带哪些过程文件?(可选)
- handoff server URL 是什么?(必填;安装时已写到 `~/.handoff/config`,不传也行)
- 过期时间?(默认 7 天)

### 步骤 2:在 A 端打包

让用户**显式**提供(或 LLM 从上下文抽)要打包的消息内容。然后:

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
- `HANDOFF_SERVER_URL`:默认 server URL(可选;通常 `~/.handoff/config` 已配好)

依赖:
- Python 3.10+
- `httpx`
- `cryptography`

安装依赖:
```bash
pip install httpx cryptography
```
