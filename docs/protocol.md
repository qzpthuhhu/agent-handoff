# Agent Handoff Protocol v1.0

> End-to-end encrypted handoff bundle protocol between AI agents.
> 服务端只看到密文,密钥只存在两端。

## 1. 设计目标

- **隐私优先**: 服务端不能读到消息内容
- **轻量**: 单次请求,小 bundle(< 10MB)直接 JSON,大 bundle 走预签名上传
- **可控**: bundle 默认 7 天过期,可配置一次性消费
- **可审计**: 服务端记录 bundle 元数据(大小、时间、过期),但不知道内容

## 2. 角色

| 角色 | 作用 |
|------|------|
| **Sender (A agent)** | 打包本地聊天记录 + 过程文件,加密,上传 |
| **Relay (服务端)** | 存密文 + 索引,不做解密 |
| **Receiver (B agent)** | 拿到 key 后拉取密文,本地解密 |
| **User** | 在 A 端拿到 `handoff_key`,人肉传给 B 端(剪贴板/IM/二维码) |

## 3. Bundle ID 与 Key

### 3.1 Bundle ID

- 16 字节随机数,hex 编码,32 字符
- 客户端生成,作为服务端定位密文的唯一 ID
- 服务端只看到 ID + 密文,不知道 ID 与 key 的关联

### 3.2 Handoff Key (用户复制)

格式:`ah-{bundle_id}.{enc_key_b64}`

- `ah-` 前缀方便识别
- `bundle_id`: 32 字符 hex
- `.`: 分隔符
- `enc_key_b64`: 32 字节随机 AES-256 key 的 URL-safe base64 编码(43 字符,无 padding)

示例:
```
ah-7f3a9b2c8e1d4f5a6b7c8d9e0f1a2b3c.dGhpcyBpcyBhIDMyLWJ5dGUgQUVTLTI1NiBrZXk
```

## 4. 加密

- 算法: **AES-256-GCM**
- Key: 32 字节随机(`secrets.token_bytes(32)`)
- Nonce: 12 字节随机,每次加密重新生成
- AAD(Additional Authenticated Data): 包含 `bundle_id`,防止密文在不同 bundle 间替换攻击
- 输出格式: `ciphertext || nonce || tag`(AES-GCM 自带 16 字节 tag)

**Payload(明文)结构**(JSON,加密前):
```json
{
  "version": "1.0",
  "created_at": "2026-07-17T16:00:00Z",
  "source": {
    "agent": "A",
    "client": "claude-desktop",
    "user": "alice"
  },
  "messages": [
    {
      "role": "user",
      "content": "...",
      "ts": "2026-07-17T15:30:00Z"
    },
    {
      "role": "assistant",
      "content": "...",
      "ts": "2026-07-17T15:30:05Z",
      "tool_calls": [...]
    }
  ],
  "files": [
    {
      "name": "report.md",
      "path": "/Users/alice/work/report.md",
      "content_b64": "...",
      "size": 1234,
      "mime": "text/markdown",
      "sha256": "..."
    }
  ],
  "metadata": {
    "n_turns": 10,
    "topic": "Q3 财务 review",
    "tags": ["finance", "review"]
  }
}
```

## 5. HTTP API

所有请求 `Content-Type: application/json`。

### 5.1 上传 bundle

```
POST /api/v1/bundles
```

请求体:
```json
{
  "id": "7f3a9b2c8e1d4f5a6b7c8d9e0f1a2b3c",
  "ciphertext_b64": "...",
  "nonce_b64": "...",
  "expires_in": 604800,
  "hint": "handoff from A to B"
}
```

成功响应(`201 Created`):
```json
{
  "id": "7f3a9b2c8e1d4f5a6b7c8d9e0f1a2b3c",
  "expires_at": "2026-07-24T16:00:00Z",
  "size": 12345
}
```

错误:
- `400`: 字段缺失或格式错误
- `413`: payload 超过服务端限制(默认 50MB)
- `429`: 速率限制(默认每 IP 每分钟 30 次)

### 5.2 拉取 bundle

```
GET /api/v1/bundles/{id}
```

成功响应(`200 OK`):
```json
{
  "id": "7f3a9b2c8e1d4f5a6b7c8d9e0f1a2b3c",
  "ciphertext_b64": "...",
  "nonce_b64": "...",
  "hint": "handoff from A to B",
  "expires_at": "2026-07-24T16:00:00Z",
  "consumed": false
}
```

错误:
- `404`: ID 不存在
- `410`: 已过期或已被消费(且配置了一次性)

### 5.3 删除 bundle(可选)

```
DELETE /api/v1/bundles/{id}
```

拉取后立即删除,适合一次性场景。需要在请求头带 admin token。

### 5.4 健康检查

```
GET /api/v1/health
```

响应:
```json
{
  "status": "ok",
  "storage": "tos",
  "version": "1.0.0"
}
```

## 6. 存储后端

### 6.1 火山引擎 TOS

- Bucket: 由用户配置(默认 `agent-handoff`)
- Object key: `bundles/{id}.bin`
- Object 内容: `ciphertext || nonce`(客户端发上来时已经拼好)
- 自定义元数据(可选): `x-handoff-hint`, `x-handoff-expires-at`

### 6.2 元数据索引(可选,SQLite)

服务端可以选择用 SQLite 索引,方便做:
- 管理后台
- 速率限制
- 过期清理

字段:`id`, `size`, `created_at`, `expires_at`, `consumed`, `hint`。

如果只跑单机最小版本,可以直接靠 TOS + 后台扫描清理,不需要 SQLite。

## 7. 过期与清理

- **过期**: 服务端在 GET 时检查 `expires_at`,过期返回 410
- **清理**: 后台 cron 任务(每 6 小时),扫到过期的 bundle,从 TOS 删除 + 索引里删
- **一次性消费**: 默认关闭(`consumable=true` 时,GET 一次后标记 consumed,二次返回 410)

## 8. 安全考虑

| 风险 | 缓解 |
|------|------|
| 密钥泄露 | 用户负责,服务端看不到 |
| 中间人 | 部署时强制 HTTPS,服务端可选 mTLS |
| Bundle ID 撞库 | 16 字节随机,2^128 空间 |
| 重放 | 一次性消费(可选) |
| 大文件 DoS | 限制单 bundle 50MB(可调) |
| 速率滥用 | 简单 IP 限速(可换 token) |

## 9. 扩展(后续)

- [ ] 多文件分片上传(>50MB)
- [ ] 预签名直传(客户端直接 PUT 到 TOS,服务端只做协调)
- [ ] 服务端辅助审计(用户在 payload 里加签名,服务端能验签但不能解密)
- [ ] WebSocket 推送(B 端订阅,key 来了直接通知)
