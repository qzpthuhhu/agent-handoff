# 架构

## 数据流

```
┌──────────────────────────────────────────────────────────────────┐
│  A agent(发送方)                                                 │
│  ┌─────────────────────┐                                         │
│  │  package_chat_      │                                         │
│  │  history(messages,  │                                         │
│  │    files,           │                                         │
│  │    server_url, ...) │                                         │
│  └──────────┬──────────┘                                         │
│             │                                                    │
│             ▼                                                    │
│  1. payload = {messages, files, metadata, source}                │
│  2. payload → JSON → bytes                                      │
│  3. bundle_id = 16B 随机 hex                                     │
│  4. enc_key = 32B 随机 bytes                                     │
│  5. nonce = 12B 随机 bytes                                       │
│  6. ciphertext = AES-256-GCM(payload, enc_key, nonce, aad=bundle_id) │
│  7. handoff_key = f"ah-{bundle_id}.{enc_key_b64}"                 │
│  8. POST /api/v1/bundles {id, ciphertext_b64, nonce_b64, ...}    │
└──────────────┬───────────────────────────────────────────────────┘
               │ HTTPS
               ▼
┌──────────────────────────────────────────────────────────────────┐
│  Relay(服务端)                                                    │
│  ┌──────────────┐  ┌──────────────────┐                          │
│  │  FastAPI     │  │  存储后端         │                          │
│  │  + 限速      │→│  local / TOS     │                          │
│  │  + 清理任务   │  │  + SQLite 索引   │                          │
│  └──────────────┘  └──────────────────┘                          │
│                                                                  │
│  服务端只看到:{id, ciphertext_b64, nonce_b64, size, expires_at}  │
│  服务端看不到:enc_key、messages 明文、files 内容、metadata 内容  │
└──────────────┬───────────────────────────────────────────────────┘
               │ HTTPS
               ▼
┌──────────────────────────────────────────────────────────────────┐
│  B agent(接收方)                                                 │
│  ┌─────────────────────┐                                         │
│  │  fetch_chat_       │                                         │
│  │  history(           │                                         │
│  │    handoff_key,     │                                         │
│  │    server_url, ...) │                                         │
│  └──────────┬──────────┘                                         │
│             │                                                    │
│             ▼                                                    │
│  1. parse handoff_key → (bundle_id, enc_key)                     │
│  2. GET /api/v1/bundles/{bundle_id} → ciphertext_b64, nonce_b64  │
│  3. payload = AES-256-GCM-decrypt(ciphertext, enc_key, nonce, aad)│
│  4. payload = JSON-parse → {messages, files, metadata, source}   │
│  5. write:                                                    │
│     - output_dir/metadata.json                                │
│     - output_dir/messages.jsonl                              │
│     - output_dir/files/{file_name}                            │
└──────────────────────────────────────────────────────────────────┘
```

## 模块划分

### 服务端 (`server/`)

- `app/main.py` — FastAPI 入口,集成 lifespan(storage + cleanup task)
- `app/config.py` — pydantic-settings,从 .env 读
- `app/models.py` — Pydantic 请求/响应模型
- `app/routes/bundles.py` — POST /api/v1/bundles, GET /api/v1/bundles/{id}, DELETE
- `app/routes/health.py` — GET /api/v1/health
- `app/cleanup.py` — 后台任务,定期扫过期 bundle 删掉
- `app/ratelimit.py` — slowapi,IP 限速
- `app/storage/base.py` — 抽象
- `app/storage/local.py` — 文件系统 + SQLite 索引
- `app/storage/tos.py` — 火山引擎 TOS + SQLite 索引

### 客户端 (`mcp-server/`)

- `server.py` — FastMCP,暴露 3 个工具
- `packager.py` — `package_and_upload(messages, files, server_url, ...)` 一站式
- `fetcher.py` — `fetch_and_decrypt(handoff_key, server_url, output_dir)` 一站式
- `crypto.py` — AES-256-GCM 包装
- `key.py` — handoff_key 编/解码

### Skill (`skill/`)

- `SKILL.md` — 给 LLM 看的说明
- `scripts/handoff.py` — CLI,复用 mcp-server 的 packager/fetcher

## 加密细节

### AES-256-GCM

```
key    = 32 bytes (256 bits)
nonce  = 12 bytes (96 bits) — 每次加密随机
aad    = bundle_id (bytes) — 防止密文在不同 bundle 间替换
input  = payload (bytes)
output = ciphertext + tag(16 bytes, GCM 自带)
```

库用 `cryptography.hazmat.primitives.ciphers.aead.AESGCM`。

### 为什么用 AAD 绑 bundle_id?

场景:攻击者截获 (bundle_A_ciphertext, bundle_B_ciphertext) 和 handoff_key_A,尝试用 key_A 去解 B 的密文。

如果不用 AAD,只要 nonce 巧合对上(2^96 概率)就可能成功。
用了 AAD 后,解 B 的密文时 AAD 不匹配,GCM 直接 InvalidTag。

### 为什么 nonce 不放在 ciphertext 里?

协议里 ciphertext 后面追加 nonce(更紧凑),但同时通过 JSON 协议上传时把 nonce 单独传(`nonce_b64` 字段)。
服务端可以按任意方式存,我们内部统一按 `ciphertext || nonce` 二进制写对象,读时按 `\n` 切分。

## 存储层

### LocalStorage

```
bundles/
  ├── {id}.bin         # ciphertext_b64 + "\n" + nonce_b64
  └── ...

index.sqlite           # 元数据索引
  bundles(id, size, created_at, expires_at, consumed, hint)
```

### TosStorage

```
TOS bucket: agent-handoff
prefix/bundles/
  ├── {id}.bin
  └── ...
```

元数据仍然用本地 SQLite(存在服务器本地,不做分布式),因为:
- SQLite 查询简单,管理后台容易做
- 跨服务实例的话用环境变量指定共享路径(单实例足够)

## 限速

`slowapi` + IP 限速,默认每 IP 每分钟 30 次。生产建议:
- 改成 token 限速(每用户)
- 或者用 nginx limit_req

## 清理任务

`cleanup.py` 的 `_tick()` 每 `cleanup_interval` 秒(默认 6 小时)跑一次:

```python
def _tick(self) -> None:
    now = datetime.now(timezone.utc)
    expired = self.storage.list_expired(now)
    for meta in expired:
        self.storage.delete(meta.id)
```

清理时同步:
- local:删 .bin + SQLite 行
- TOS:DeleteObject + SQLite 行

## 协议 v1.0 局限 & 后续

| 局限 | 缓解 / 后续 |
|------|------|
| 单 bundle ≤ 50MB | 后续:分片 / 预签名直传 |
| 不能增量更新 | v2:支持 bundle append |
| 没审计 | 后续:用户在 payload 加签名,服务端能验签但不能解密 |
| 单 region | TOS 跨区复制,或服务端多 region |
| SQLite 单机 | 后续:换 PostgreSQL(但本项目预期单机/小规模) |
