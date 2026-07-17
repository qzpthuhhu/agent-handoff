# agent-handoff

> 在两个 AI agent 之间**端到端加密**地传递聊天记录和过程文件。
> 服务端只看到密文,密钥只在你和目标 agent 手里。

适合 Claude Desktop / Cursor / Cline / 自研 agent 之间共享上下文。

```
┌─────────────┐  加密    ┌──────────┐   密文    ┌─────────────┐
│  A agent    │ ───────► │  Relay   │ ◄─────── │  B agent    │
│  (sender)   │  upload  │  (server)│  fetch   │  (receiver) │
└─────────────┘          └──────────┘          └─────────────┘
       │                       │                      │
       └──── handoff_key (ah-xxx.yyy) ────────────────┘
                       用户复制粘贴
```

## 核心特性

- 🔐 **端到端加密** — AES-256-GCM,bundle id 和 key 完全独立,服务端无法还原
- 🤖 **MCP + Skill 双形态** — Claude Desktop / Cursor 用 MCP,不兼容 MCP 的平台用 Skill CLI
- 📦 **自带打包** — 一条调用把"最近 N 轮对话 + 过程文件"打包好
- ☁️ **TOS / 本地存储** — 火山引擎对象存储 或 单机本地文件
- ⏱️ **自动过期** — bundle 默认 7 天过期,后台任务清理
- 📊 **管理简单** — 暴露 health / delete 接口,容易接入监控

## 目录结构

```
agent-handoff/
├── server/                      # 云端 Relay(FastAPI)
│   ├── app/
│   │   ├── main.py             # 入口
│   │   ├── config.py
│   │   ├── models.py
│   │   ├── cleanup.py          # 过期清理后台任务
│   │   ├── ratelimit.py
│   │   ├── routes/             # upload / fetch / delete / health
│   │   └── storage/            # 抽象 + local + tos
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── agent-handoff.service   # systemd unit
│   ├── requirements.txt
│   ├── requirements-tos.txt    # TOS 后端的可选依赖
│   └── .env.example
├── mcp-server/                  # MCP 客户端(给 A/B agent 用)
│   ├── src/agent_handoff_mcp/
│   │   ├── server.py           # FastMCP 入口
│   │   ├── packager.py         # 打包 + 加密
│   │   ├── fetcher.py          # 拉取 + 解密
│   │   ├── crypto.py
│   │   └── key.py
│   ├── pyproject.toml
│   └── README.md
├── skill/                       # Skill 版(轻量备选)
│   ├── SKILL.md
│   ├── scripts/
│   │   ├── handoff.py          # CLI: package / fetch / inspect / server
│   │   └── handoff.sh
│   └── README.md
├── tests/                       # 单元 + 端到端测试
│   ├── conftest.py
│   ├── test_crypto.py
│   └── test_server.py
├── examples/
│   └── e2e_demo.py             # 端到端演示(无需起 server)
├── docs/
│   ├── protocol.md
│   └── deployment.md
├── requirements-dev.txt
└── README.md
```

## 快速上手

### 1. 部署 Relay(在 ECS 上)

最简单的方式 — Docker:

```bash
cd server
cp .env.example .env
# 编辑 .env,设置 ADMIN_TOKEN,以及 TOS 配置(若用对象存储)
docker compose up -d
# 等几秒,验证
curl http://localhost:8080/api/v1/health
# 期望:{"status":"ok","storage":"local","version":"1.0.0"}
```

其他部署方式(Docker / systemd / 裸机)详见 [`docs/deployment.md`](docs/deployment.md)。

### 2. A 端发送

#### 用 MCP(推荐,Claude Desktop / Cursor)

编辑 `claude_desktop_config.json`:

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

然后在 A 端对话里:

> 用户:"把前 10 轮对话打包给 B"
>
> LLM:调用 `package_chat_history(messages=[...], server_url="http://your-ecs:8080", files=[...])`
>
> LLM:返回 handoff key,让用户复制。

#### 用 Skill(不兼容 MCP 的平台)

```bash
cd skill
./scripts/handoff.sh package \
  --server-url http://your-ecs:8080 \
  --messages-json ./messages.json \
  --files ./report.md
```

### 3. 用户复制 handoff key

```
ah-7f3a9b2c8e1d4f5a6b7c8d9e0f1a2b3c.dGhpcyBpcyBhIDMyLWJ5dGUgQUVTLTI1NiBrZXk
```

通过剪贴板 / 飞书 / 邮件 / 任意渠道发给 B 端。

### 4. B 端接收

MCP 工具:`fetch_chat_history(handoff_key="ah-...", server_url="http://your-ecs:8080")`

或者 Skill:
```bash
./scripts/handoff.sh fetch \
  --server-url http://your-ecs:8080 \
  --handoff-key "ah-..." \
  --output-dir ./handoff
```

输出目录结构:
```
./handoff/
├── metadata.json
├── messages.jsonl      # ← B 端 LLM 读这个接上文
└── files/
    └── report.md        # ← 还原的过程文件
```

## 端到端演示

不依赖外部 server,直接用 TestClient 跑完整流程:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r server/requirements.txt -r requirements-dev.txt
python examples/e2e_demo.py
```

期望看到:
- A 端生成 handoff key
- B 端拉取并解密
- 消息和文件完全还原
- 服务端只看到 base64 密文

## 测试

```bash
pytest tests/ -v
# 12 passed in <1s
```

## 协议

详见 [`docs/protocol.md`](docs/protocol.md)。

要点:
- Handoff key 格式:`ah-{bundle_id_hex}.{enc_key_b64}`
- 加密:AES-256-GCM,nonce 12 字节,key 32 字节,AAD 绑定 bundle_id
- 存储:密文(包含 nonce)+ 元数据(不含明文)
- 默认 7 天过期,可配一次性消费

## 安全模型

- **服务端**:只看到 base64 密文 + bundle_id + 大小 + 过期时间。不知道 key,看不到明文
- **handoff key**:只存在于用户剪贴板 / 接收方内存。绝不进服务端
- **中间人**:部署时强制 HTTPS(或 mTLS)。服务端可选 IP 限速
- **bundle id 撞库**:16 字节随机 = 2^128 空间
- **可选**:服务端开启 `ONE_TIME_CONSUME=true` 后,GET 一次后立即失效

## 配置项

服务端 `.env`:

| 变量 | 说明 | 默认 |
|------|------|------|
| `STORAGE_BACKEND` | `local` 或 `tos` | `local` |
| `TOS_*` | 火山引擎 TOS 配置 | - |
| `MAX_BUNDLE_SIZE` | 单 bundle 字节上限 | 50MB |
| `DEFAULT_EXPIRES_IN` | 默认过期秒数 | 7 天 |
| `ONE_TIME_CONSUME` | GET 一次后失效 | false |
| `ADMIN_TOKEN` | 强制删除的 token | (必改) |
| `RATE_LIMIT_PER_MIN` | 每 IP 限速 | 30 |

## 协议版本

v1.0 — 当前

## License

MIT
