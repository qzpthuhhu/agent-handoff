# 部署指南

## 方式 1:Docker(推荐)

### 1.1 准备工作

- 一台 ECS(2C2G 够用,流量小)
- 公网 IP(让 A/B 端能访问)
- 域名 + HTTPS(强烈建议,生产必备;可以用 nginx 反代 + Let's Encrypt)

### 1.2 本地存储(快速验证)

```bash
cd server
cp .env.example .env
# 编辑 .env,改 ADMIN_TOKEN 为一个长随机字符串
sed -i '' 's/^ADMIN_TOKEN=.*/ADMIN_TOKEN=你的长随机字符串/' .env

# 起
docker compose up -d
docker compose logs -f
# 等看到 "starting agent-handoff"

# 验证
curl http://localhost:8080/api/v1/health
# 期望:{"status":"ok","storage":"local","version":"1.0.0"}
```

数据在 Docker volume `handoff-data`,可用 `docker volume inspect handoff-data` 查路径。

### 1.3 火山引擎 TOS 存储(生产)

```bash
cd server
cp .env.example .env
# 编辑 .env,改这几行:
#   STORAGE_BACKEND=tos
#   TOS_ENDPOINT=tos-cn-beijing.volces.com  # 按你的 region
#   TOS_BUCKET=agent-handoff
#   TOS_ACCESS_KEY=你的AK
#   TOS_SECRET_KEY=你的SK
#   ADMIN_TOKEN=长随机字符串
```

构建镜像时确保装上 TOS SDK(`requirements-tos.txt` 已经在 Dockerfile 里),然后:

```bash
docker compose build --no-cache
docker compose up -d
```

首次启动会创建 bucket(如果不存在),并对 TOS 走标准 ListBucket / PutObject / GetObject 权限。

### 1.4 HTTPS(Nginx 反代)

```nginx
server {
    listen 443 ssl;
    server_name handoff.your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/handoff.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/handoff.your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # 大 bundle
        client_max_body_size 60m;
    }
}
```

## 方式 2:systemd(裸机部署)

适合长期跑、不想用容器的场景。

### 2.1 准备用户和目录

```bash
sudo useradd --system --home /opt/agent-handoff --shell /usr/sbin/nologin handoff
sudo mkdir -p /opt/agent-handoff /var/lib/agent-handoff
sudo chown -R handoff:handoff /opt/agent-handoff /var/lib/agent-handoff
```

### 2.2 部署代码

```bash
# 在本机构建(或者直接 rsync 整个项目)
cd /opt/agent-handoff
python3 -m venv .venv
sudo -u handoff .venv/bin/pip install -r server/requirements.txt
# 如果用 TOS:
sudo -u handoff .venv/bin/pip install -r server/requirements-tos.txt
sudo rsync -av --exclude='.venv' --exclude='__pycache__' /path/to/agent-handoff/server/ .
sudo chown -R handoff:handoff /opt/agent-handoff
```

### 2.3 配置 .env

```bash
sudo -u handoff cp .env.example .env
sudo -u handoff vim .env  # 改 STORAGE_BACKEND / TOS_* / ADMIN_TOKEN
```

### 2.4 安装 systemd unit

```bash
sudo cp agent-handoff.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now agent-handoff
sudo systemctl status agent-handoff
```

查看日志:

```bash
sudo journalctl -u agent-handoff -f
```

## 方式 3:直接 uvicorn(开发)

```bash
cd server
pip install -r requirements.txt -r requirements-tos.txt
cp .env.example .env
# 编辑 .env
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## 部署后验证

```bash
# 健康检查
curl -s http://localhost:8080/api/v1/health | jq
# 期望:{"status":"ok","storage":"local","version":"1.0.0"}

# 速率限制
for i in {1..40}; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/api/v1/health; done | sort | uniq -c
# 期望:大部分 200,最后几个 429

# 上传一个空 bundle 测试(实际不能用,只是看签名链路)
curl -X POST http://localhost:8080/api/v1/bundles \
  -H "Content-Type: application/json" \
  -d '{"id":"a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4","ciphertext_b64":"AA==","nonce_b64":"AAAAAAAAAAAAAAAA"}'
# 期望:201
```

## 监控建议

- **健康检查**:GET /api/v1/health — 挂到负载均衡的健康检查
- **资源**:CPU < 50%,内存 < 200MB(单 bundle 50MB 限制下)
- **存储**:
  - local 模式:监控 `/var/lib/agent-handoff` 目录大小
  - TOS 模式:监控 bucket 大小,设生命周期规则自动清理
- **日志**:Docker 用 `docker logs`;systemd 用 `journalctl -u agent-handoff`
- **告警项**:
  - 服务不可用(连续 3 次 health 失败)
  - TOS bucket size 超过 N GB
  - 持续 429(可能被滥用)

## 升级

```bash
# Docker
cd /opt/agent-handoff
git pull  # 或者重新拷贝
cd server
docker compose build --no-cache
docker compose up -d

# systemd
cd /opt/agent-handoff
git pull
sudo -u handoff .venv/bin/pip install -r server/requirements.txt
sudo systemctl restart agent-handoff
```

## 备份

- **local 模式**:tar 整个 `/var/lib/agent-handoff`(主要是 .bin + index.sqlite)
- **TOS 模式**:开 TOS 的跨区复制 / 备份策略

## 故障排查

### 服务起不来

```bash
# Docker
docker compose logs --tail=100

# systemd
sudo journalctl -u agent-handoff -n 100 --no-pager
```

常见:
- `TOS 模式必须配置 TOS_ACCESS_KEY` → 检查 .env
- `找不到 tos SDK` → `pip install -r server/requirements-tos.txt`
- `bind: address already in use` → 改 PORT

### A 端上传 413

bundle 太大。改 `MAX_BUNDLE_SIZE`。

### B 端拉取 404

- key 复制错了
- bundle 已过期(超过 `expires_in`)

### B 端拉取成功但解密失败

- key 和 bundle_id 不匹配(用了别的 bundle 的 key)
- 密文被篡改(检查链路)

### TOS 模式报权限错误

- 检查 AK/SK
- AK 必须有 PutObject / GetObject / DeleteObject / ListBucket 权限
- bucket 不存在会自动创建,需要 AK 有 CreateBucket 权限(或者预创建)
