# agent-handoff Skill

轻量备选,适合不支持 MCP 但支持 Skill 脚本调用的 agent 平台。

## 目录

```
skill/
├── SKILL.md              # 给 LLM 看的说明(主入口)
├── scripts/
│   ├── handoff.py        # CLI 工具:package / fetch / inspect / server
│   └── handoff.sh        # shell 包装,走 handoff.py
└── README.md
```

## 快速使用

```bash
# 打包(发送端)
./scripts/handoff.sh package \
  --server-url http://your-ecs:8080 \
  --messages-json ./messages.json \
  --files ./report.md,./data.csv \
  --hint "Q3 review handoff"

# 拉取(接收端)
./scripts/handoff.sh fetch \
  --server-url http://your-ecs:8080 \
  --handoff-key "ah-..." \
  --output-dir ./handoff

# 校验 key
./scripts/handoff.sh inspect --handoff-key "ah-..."

# 启动本地 server(开发用)
./scripts/handoff.sh server --port 8080
```

## 与 MCP 的关系

两者功能等价。Skill 版本就是一个 Python CLI,可以被任何能跑命令的 agent 调用。MCP 版本更标准化,适合 Claude Desktop / Cursor / Cline。

代码层面 Skill 复用了 MCP 客户端的 `packager` / `fetcher` / `key` 模块,不重复实现加密层。

## 依赖

```bash
pip install httpx cryptography
```
