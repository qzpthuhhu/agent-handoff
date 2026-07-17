# syntax=docker/dockerfile:1.6
#
# Build context 必须是项目根(由 docker-compose.yml 设定)
# 这样可以同时 COPY server/ 和 skill/ 的内容

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 安装基础依赖
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 可选:装 TOS SDK(默认装,精简镜像可以删除这一行后用 docker-compose 控制)
COPY server/requirements-tos.txt .
RUN pip install --no-cache-dir -r requirements-tos.txt || true

# 拷 server 代码
COPY server/app ./app

# 拷 skill 资产(供 /install 路由 base64 嵌入到安装脚本里)
COPY skill /install

# 拷 mcp-server 模块源码(供 /install 路由打包成 tarball 给客户端)
COPY mcp-server/src/agent_handoff_mcp /install/mcp_src

# 运行时数据目录
RUN mkdir -p /var/lib/agent-handoff

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
