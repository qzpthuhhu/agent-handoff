# syntax=docker/dockerfile:1.6

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 安装基础依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 可选:装 TOS SDK(默认装,精简镜像可以删除这一行后用 docker-compose 控制)
COPY requirements-tos.txt .
RUN pip install --no-cache-dir -r requirements-tos.txt || true

# 拷代码
COPY app ./app

# 运行时数据目录
RUN mkdir -p /var/lib/agent-handoff

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
