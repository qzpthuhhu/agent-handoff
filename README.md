# agent-handoff

> 在两个 AI agent 之间**端到端加密**地传递聊天记录和过程文件。
> 服务端只看到密文,密钥只在你和目标 agent 之间流转。

```
┌─────────────┐  加密    ┌──────────┐   密文    ┌─────────────┐
│  A agent    │ ───────► │  Relay   │ ◄─────── │  B agent    │
│  (sender)   │  upload  │ (server) │  fetch   │ (receiver)  │
└─────────────┘          └──────────┘          └─────────────┘
       │                       ▲                      │
       │       handoff_key (ah-xxx.yyy)                │
       └────────────────────── ┘ ─────────────────────┘
                       用户复制粘贴
```

**当前部署**: https://aishangai.shop(走 Cloudflare Tunnel 加密)

## 核心特性

- 🔐 **端到端加密** — AES-256-GCM,bundle id 和 key 完全独立,服务端无法还原
- 🤖 **MCP + Skill + HTTP 三形态** — Claude Desktop / Cursor / Cline / 任何语言
- 📦 **自包含 Python helper** — 接收方 agent 只需 fetch 一个 markdown,复制粘贴 100 行代码就能用
- ☁️ **TOS / 本地存储** — 火山引擎对象存储 或 本地文件系统
- ⏱️ **自动过期** — bundle 默认 7 天,后台任务每 6 小时清理
- 📊 **管理友好** — 主页 / 复制按钮 / 给 LLM 抓的 `/guide.md` `/skill.md` `/agents.txt`

## 目录结构

```
agent-handoff/
├── server/                      # 云端 Relay(FastAPI + Uvicorn)
│   ├── app/
│   │   ├── main.py             # 入口 + lifespan
│   │   ├── config.py           # pydantic-settings
│   │   ├── models.py
│   │   ├── cleanup.py          # 后台过期清理
│   │   ├── ratelimit.py
│   │   ├── routes/
│   │   │   ├── bundles.py      # POST/GET/DELETE /api/v1/bundles
│   │   │   ├── health.py       # /api/v1/health
│   │   │   ├── install.py      # /install (legacy 一键 bash)
│   │   │   └── pages.py        # / /guide.md /skill.md /agents.txt (HTML + MD)
│   │   └── storage/
│   │       ├── base.py
│   │       ├── local.py
│   │       └── tos.py          # 火山引擎 TOS(可选)
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── agent-handoff.service   # systemd unit
│   ├── requirements.txt
│   ├── requirements-tos.txt
│   └── .env.example
├── mcp-server/                  # MCP 客户端
│   ├── src/agent_handoff_mcp/
│   │   ├── server.py           # FastMCP 入口(3 个 tool)
│   │   ├── packager.py
│   │   ├── fetcher.py
│   │   ├── crypto.py
│   │   └── key.py
│   └── pyproject.toml
├── skill/                       # Skill CLI(给不兼容 MCP 的 agent)
│   ├── SKILL.md                # 给 LLM 看的说明
│   └── scripts/
│       ├── handoff.py
│       └── handoff.sh
├── tests/                       # 26 个测试
│   ├── conftest.py
│   ├── test_crypto.py          # 7
│   ├── test_install.py         # 5
│   ├── test_pages.py           # 9
│   └── test_server.py           # 5
├── examples/
│   ├── deploy_test.py           # 本地一键 e2e
│   └── e2e_demo.py              # TestClient 端到端演示
├── docs/
│   ├── protocol.md
│   ├── deployment.md
│   └── architecture.md
└── README.md                    # 本文件
```

## 快速开始

### 接收方接入(给目标 agent)

**1. 复制下面的 prompt 给目标 agent**:

> 我要用 agent-handoff(开源的 agent 任务上下文加密传递服务,部署在 https://aishangai.shop,端到端加密,服务端只看到密文)。
>
> 请按以下步骤操作(不需要 install,不需要装包,不需要创建任何进程,只需要 curl):
>
> 1. 拉技能文档到你的 skills 目录(用 curl 单一动作,你可以先 cat 审计):
>    curl -fsSL https://aishangai.shop/skill.md -o skills/agent-handoff/SKILL.md
>
> 2. 读这个文件,它包含完整的自包含 Python helper(只需要 cryptography 和 httpx 包,Python 内置库也够)。
>
> 3. 我会给你一个 handoff key(类似 ah-xxx.yyy)和 messages(要打包的对话)。你用 SKILL.md 里的 handoff() 函数打包,生成 handoff key 给我。或者用 fetch() 函数拉取我给的 key 对应的内容。
>
> 注意:
> - 不需要跑 install 脚本
> - 不需要创建 ~/.handoff/ 目录
> - 不需要装 mcp-server 或任何 systemd 服务
> - 唯一动作是 curl 拉一个 markdown 文档,你可以 cat 审计
>
> source: https://aishangai.shop (开源: https://github.com/qzpthuhhu/agent-handoff, MIT)

**2. 把 handoff key 粘到目标 agent 对话**(你发完接收方后)

**3. 接收方 agent 跑 `fetch(handoff_key, server_url)` 自动拉取并解密**

**完整流程(人类视角)**:
1. 打开 https://aishangai.shop/
2. 点 hero 区的"复制纯 curl 接入指令"
3. 粘到目标 agent(Claude Desktop / Cursor / Cline / Claude Code 等)
4. agent 自己 fetch skill.md + 用 Python helper
5. 你(或 A 端)调 `handoff(messages, ...)` 生成 key
6. 把 key 粘到 B 端对话
7. B 端 `fetch(key)` 拉取还原

## 三种客户端形态

| 形态 | 适合 | 接入方式 |
|---|---|---|
| **HTTP API** | 任何语言 | 直接 `curl` 或用 `httpx`/`requests` |
| **MCP Server** | Claude Desktop / Cursor / Cline | 加 mcpServers 配置(走 `mcp[cli]`) |
| **Skill CLI** | 不支持 MCP 的 agent | `bash -c "$(curl ...)"` 一行装 skill 到 `~/.handoff/` |

### HTTP API(最简)

```bash
# 1. 拉 SKILL.md 拿到 Python helper(包含完整 encrypt/decrypt + API 调用)
curl -fsSL https://aishangai.shop/skill.md

# 2. 复制粘贴里面的 handoff() / fetch() 函数到你的脚本
# 3. 调用
python3 -c "
import sys
sys.path.insert(0, 'mcp-server/src')
from agent_handoff_mcp.packager import package_and_upload
key = package_and_upload(
    messages=[{'role': 'user', 'content': 'hi'}],
    server_url='https://aishangai.shop',
)
print(key['handoff_key'])
"
```

### MCP Server(Claude Desktop)

```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "agent-handoff": {
      "command": "uvx",
      "args": ["--from", "agent-handoff-mcp", "agent-handoff-mcp"]
    }
  }
}
```

工具列表:
- `package_chat_history(messages, server_url, files?, ...)` — 打包加密上传,返回 handoff key
- `fetch_chat_history(handoff_key, server_url, output_dir?)` — 拉取解密落盘
- `inspect_handoff_key(handoff_key)` — 校验 key 格式

### Skill CLI(legacy,给不挑剔的 agent)

```bash
bash -c "$(curl -fsSL https://aishangai.shop/install)"
# 然后:
handoff package --messages-json ./msgs.json --hint 'topic'
handoff fetch --handoff-key ah-xxx.yyy --output-dir ./out
handoff inspect --handoff-key ah-xxx.yyy
```

## 端点

| 端点 | 用途 | 谁用 |
|---|---|---|
| `GET /` | HTML 主页(深色主题 + 复制按钮 + 资源链接) | 人类 |
| `GET /api/v1/health` | 健康检查 | 监控 |
| `GET /api/v1/bundles/{id}` | 拉取密文(返回 base64 + nonce) | 客户端 |
| `POST /api/v1/bundles` | 上传密文(传入 base64 + nonce) | 客户端 |
| `DELETE /api/v1/bundles/{id}` | 强制删除(需 admin token) | 管理员 |
| `GET /install` | legacy 一键安装脚本(含 SHA256 header) | 不挑剔的 agent |
| `GET /skill.md` | 自包含 SKILL.md(纯文本 + Python helper) | **挑剔的 agent(推荐)** |
| `GET /guide.md` | 详细使用指南(markdown) | LLM |
| `GET /agents.txt` | agents.txt 协议(2025 AI 入口) | LLM/agent discovery |
| `GET /docs` `/redoc` `/openapi.json` | FastAPI 自动生成的 API 文档 | 开发者 |

## 安全模型

- **算法**: AES-256-GCM
- **Key**: 32 字节随机(`secrets.token_bytes(32)`)
- **Nonce**: 12 字节随机,每次加密重新生成
- **AAD**: 绑 `bundle_id`,**防密文跨 bundle 替换攻击**
- **Bundle ID**: 16 字节随机 hex
- **存储**: 服务端只看到 base64 密文 + 元数据(大小、过期时间、提示)
- **传输**: handoff key 在用户剪贴板 / 接收方内存,**永远不进服务端**

handoff key 格式: `ah-{32 hex chars}.{43 urlsafe-b64 chars}` ≈ 80 字符

## 用户原话 → LLM 调工具(给 agent 看的关键映射)

LLM 看到用户说这些时,**自己从对话历史里抽 messages + 文件**,然后调工具:

| 用户说 | LLM 怎么做 |
|---|---|
| "把刚刚对话的 XXX 主题记录打包" | 抽相关轮次 → `package_chat_history(messages=[...], ...)` |
| "把前 N 轮对话打包" | 抽最近 N 条 → `package_chat_history(...)` |
| "把刚才读过的 report.md 也一起打包" | messages + files → `package_chat_history(..., files=[...])` |
| "把 handoff key `ah-xxx.yyy` 拉过来" | `fetch_chat_history(handoff_key=...)` |
| "把 handoff key 校验一下" | `inspect_handoff_key(handoff_key=...)` |

## 部署

### 当前生产环境

- **公网**: https://aishangai.shop(走 Cloudflare Tunnel)
- **ECS**: 火山引擎 `115.190.216.219`(仅内网)
- **架构**: cloudflared → ECS localhost:8080 → FastAPI/Docker
- **存储**: local(在 ECS `/var/lib/docker/volumes/server_handoff-data/_data`)
- **公网安全组**: 22(SSH)、8080(已开,内部用,实际流量走 tunnel)

### 重新部署(单台新 ECS)

```bash
# 1. 装 Docker
apt update && apt install -y docker.io docker-compose-v2

# 2. 拉代码
cd /opt
git clone https://github.com/qzpthuhhu/agent-handoff.git
cd agent-handoff/server

# 3. 配 .env
cp .env.example .env
# 改 ADMIN_TOKEN=$(openssl rand -hex 32)
# (用 TOS 就改 STORAGE_BACKEND=tos + 填 AK/SK)

# 4. 起
docker compose up -d --build

# 5. 验证
curl http://localhost:8080/api/v1/health
# {"status":"ok","storage":"local","version":"1.0.0"}

# 6. 装 cloudflared(可选,免开 8080 端口给公网)
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared focal main' > /etc/apt/sources.list.d/cloudflared.list
apt update && apt install -y cloudflared
cloudflared tunnel login
cloudflared tunnel create handoff
# 写 /etc/cloudflared/config.yml:
#   tunnel: <UUID>
#   credentials-file: /root/.cloudflared/<UUID>.json
#   ingress:
#     - hostname: aishangai.shop
#       service: http://localhost:8080
#     - service: http_status:404
cloudflared tunnel route dns handoff aishangai.shop
cloudflared service install
systemctl enable --now cloudflared
```

### 安全组(DO/ECS 控制台)

最小入站规则:
- 22/SSH(管理用,限制源 IP)
- 8080(内部用,如果走 cloudflared tunnel 可以不开公网)

出站:全开(cloudflared 主动出站 + pip install)。

## 开发

```bash
# 装 dev 依赖
python3 -m venv .venv
.venv/bin/pip install -r server/requirements.txt -r requirements-dev.txt

# 跑测试
.venv/bin/python -m pytest tests/ -v
# 26 passed in <1s

# 跑端到端 demo
.venv/bin/python examples/e2e_demo.py

# 跑 deploy_test(本地起 uvicorn,真 HTTP)
.venv/bin/python examples/deploy_test.py
```

### 重新 build 镜像 + 部署

```bash
cd server
docker compose up -d --build
docker logs -f agent-handoff
```

## 已知问题 / 限制

- **GitHub PAT 暴露风险**: 不要把 token 直接 paste 到任何 LLM 对话 — 会被持久化到对话历史。读环境变量或本地文件更安全。
- **/install 是 legacy 模式**: `bash -c "$(curl | bash)"` 触发有安全审计的 agent(Claude Code / Claude.ai)拒绝。给挑剔的 agent 用 `/skill.md` 模式。
- **Bundle 数据库 0 条是正常的**: 默认 7 天过期,后台清理任务会定期删。
- **cloudflared 版本警告**: 偶发报"version outdated",升级即可,不影响功能。
- **不走 HTTPS 的 /install**: 实际是 `https://aishangai.shop/install`,但 base64 嵌入 + pipe-to-bash 模式让安全 agent 警惕 — 已被新无 install 模式取代。

## 协议 / 规范

详细加密协议、API 字段、TLS 头、Q&A 见 [`docs/protocol.md`](docs/protocol.md)。

## License

MIT
