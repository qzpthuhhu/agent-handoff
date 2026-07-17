# agent-handoff-mcp

MCP Server 端,让任何支持 MCP 的 agent(Claude Desktop / Cursor / Cline / 自研)在对话里直接调用 `package_chat_history` 和 `fetch_chat_history`,把聊天记录 + 过程文件加密后传给另一个 agent。

## 工具列表

| 工具 | 作用 | 调用方 |
|------|------|--------|
| `package_chat_history` | 打包 + 加密 + 上传,返回 handoff key | A 端 |
| `fetch_chat_history` | 拉取 + 解密 + 落盘 | B 端 |
| `inspect_handoff_key` | 校验 key 格式(不实际拉取) | 任意 |

## 安装

### 方式 1:`uvx`(推荐,免装)

```bash
# 先装好 uv
uvx --from "agent-handoff-mcp" agent-handoff-mcp
```

### 方式 2:`pip install`

```bash
pip install agent-handoff-mcp
# 然后跑:
agent-handoff-mcp
```

## 在 Claude Desktop 注册

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`(macOS)或 `%APPDATA%\Claude\claude_desktop_config.json`(Windows):

```json
{
  "mcpServers": {
    "agent-handoff": {
      "command": "uvx",
      "args": ["--from", "agent-handoff-mcp", "agent-handoff-mcp"]
    }
  }
}
```

如果用 pip 安装:

```json
{
  "mcpServers": {
    "agent-handoff": {
      "command": "agent-handoff-mcp"
    }
  }
}
```

## 在 Cursor 注册

`Cursor Settings → MCP → Add new global MCP server`,填:

```
Name: agent-handoff
Command: uvx
Args: --from agent-handoff-mcp agent-handoff-mcp
```

## 调用示例

### A 端打包

让 agent 调用:

```
package_chat_history(
  messages=[
    {"role": "user", "content": "帮我分析 Q3 财报", "ts": "2026-07-17T15:00:00Z"},
    {"role": "assistant", "content": "好的,我先看一下...", "ts": "2026-07-17T15:00:05Z"},
    ...
  ],
  files=["/Users/me/work/q3-report.pdf"],
  server_url="https://handoff.example.com",
  metadata={"topic": "Q3 finance review"},
  expires_in=259200  // 3 天
)
```

返回里会有一行 `📋 handoff_key`,复制给 B 端。

### B 端拉取

```
fetch_chat_history(
  handoff_key="ah-7f3a9b2c....dGhpcyBpcw",
  server_url="https://handoff.example.com",
  output_dir="/Users/other/work/handoff"
)
```

返回里有落盘目录 + 消息 jsonl + 文件列表。

## 协议

见 [`docs/protocol.md`](../docs/protocol.md)。
