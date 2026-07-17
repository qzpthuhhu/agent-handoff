"""端到端测试:启动 server,packager 上传,fetcher 拉取,比对内容。

用 TestClient 跑 FastAPI,不实际起 uvicorn。
用 httpx.MockTransport 把 packager/fetcher 内部 httpx 调用桥接到 TestClient。
"""
from __future__ import annotations

import base64
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Iterator

import httpx
import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mcp-server" / "src"))
sys.path.insert(0, str(_ROOT / "server"))

from fastapi.testclient import TestClient  # noqa: E402

# 在 import app 之前先注入临时配置
_TMP = Path(tempfile.mkdtemp(prefix="handoff-test-"))
import os  # noqa: E402

os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_DIR"] = str(_TMP / "bundles")
os.environ["LOCAL_INDEX_DB"] = str(_TMP / "index.sqlite")
os.environ["ADMIN_TOKEN"] = "test-admin-token"

# 必须在改 env 之后 import
import app.config as _cfg  # noqa: E402

_cfg.get_settings.cache_clear()

from app.main import create_app  # noqa: E402

from agent_handoff_mcp import fetcher, packager  # noqa: E402


@pytest.fixture
def test_client_factory():
    """返回一个带 httpx.MockTransport 的 TestClient。

    用法:`test_client, server_url = test_client_factory`
    """
    app = create_app()
    # 必须用 with 上下文,触发 lifespan(初始化 storage/cleanup)
    with TestClient(app) as test_client:
        def _request_handler(request: httpx.Request) -> httpx.Response:
            return test_client.request(
                method=request.method,
                url=request.url,
                json=json.loads(request.content) if request.content else None,
                headers=request.headers,
            )

        transport = httpx.MockTransport(_request_handler)
        real_client = httpx.Client(transport=transport, base_url="http://testserver")

        # 临时替换 packager/fetcher 里的 httpx.post/get
        orig_post = httpx.post
        orig_get = httpx.get

        def _patched_post(url, **kw):
            return real_client.post(url, **kw)

        def _patched_get(url, **kw):
            return real_client.get(url, **kw)

        httpx.post = _patched_post
        httpx.get = _patched_get
        try:
            yield test_client, "http://testserver"
        finally:
            httpx.post = orig_post
            httpx.get = orig_get
            real_client.close()


def test_health(test_client_factory) -> None:
    client, _ = test_client_factory
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["storage"] == "local"


def test_full_handoff_roundtrip(test_client_factory, tmp_path: Path) -> None:
    _client, server_url = test_client_factory

    # 准备源文件
    src_file = tmp_path / "report.md"
    src_file.write_text("# Q3 Report\n\nRevenue +20%\n", encoding="utf-8")

    # 构造 messages
    messages = [
        {"role": "user", "content": "帮我分析 Q3 财报", "ts": "2026-07-17T15:00:00Z"},
        {"role": "assistant", "content": "我看了 report,营收增长 20%。", "ts": "2026-07-17T15:00:10Z"},
        {"role": "user", "content": "把 handoff 给 B 继续做", "ts": "2026-07-17T15:01:00Z"},
    ]

    result = packager.package_and_upload(
        messages=messages,
        server_url=server_url,
        files=[str(src_file)],
        metadata={"topic": "Q3 review"},
        hint="from A to B",
        source={"client": "test", "user": "alice"},
    )
    assert "handoff_key" in result
    handoff_key = result["handoff_key"]
    assert result["n_messages"] == 3
    assert result["n_files"] == 1

    # B 端拉取
    output_dir = tmp_path / "handoff-out"
    summary = fetcher.fetch_and_decrypt(
        handoff_key=handoff_key,
        server_url=server_url,
        output_dir=str(output_dir),
    )
    assert summary["n_messages"] == 3
    assert summary["n_files"] == 1

    # 验证消息内容
    msgs = []
    with open(summary["messages"], "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                msgs.append(json.loads(line))
    assert msgs[0]["content"] == "帮我分析 Q3 财报"
    assert msgs[1]["content"] == "我看了 report,营收增长 20%。"

    # 验证文件还原
    restored = Path(summary["files"][0])
    assert restored.read_text(encoding="utf-8") == src_file.read_text(encoding="utf-8")

    # 验证 metadata
    meta = json.loads(Path(summary["metadata"]).read_text(encoding="utf-8"))
    assert meta["metadata"]["topic"] == "Q3 review"
    assert meta["source"]["client"]  # 至少有 client 字段


def test_wrong_key_fails(test_client_factory, tmp_path: Path) -> None:
    """用错的 key 拉取应该解密失败。"""
    _client, server_url = test_client_factory
    messages = [{"role": "user", "content": "hi"}]
    result = packager.package_and_upload(messages=messages, server_url=server_url)
    real_key = result["handoff_key"]

    # 改一位:把 enc_key 末位换掉(bid 段已经含 ah- 前缀)
    bid, enc = real_key.split(".", 1)
    bad_char = "A" if enc[-1] != "A" else "B"
    bad_key = f"{bid}.{enc[:-1]}{bad_char}"
    assert bad_key != real_key
    with pytest.raises(fetcher.FetchError):
        fetcher.fetch_and_decrypt(
            handoff_key=bad_key,
            server_url=server_url,
            output_dir=str(tmp_path / "bad"),
        )


def test_bundle_not_found(test_client_factory, tmp_path: Path) -> None:
    """不存在的 bundle id 应该报 404。"""
    _client, server_url = test_client_factory
    fake_key = f"ah-{'0' * 32}.{base64.urlsafe_b64encode(b'x' * 32).rstrip(b'=').decode()}"
    with pytest.raises(fetcher.FetchError):
        fetcher.fetch_and_decrypt(
            handoff_key=fake_key,
            server_url=server_url,
            output_dir=str(tmp_path / "nope"),
        )


def test_oversize_rejected(test_client_factory) -> None:
    """超过 max_bundle_size 的请求应该被拒。"""
    client, _ = test_client_factory
    settings = _cfg.get_settings()
    settings.max_bundle_size = 100  # 100 字节

    big = base64.b64encode(b"x" * 200).decode("ascii")
    resp = client.post(
        "/api/v1/bundles",
        json={
            "id": "a" * 32,
            "ciphertext_b64": big,
            "nonce_b64": base64.b64encode(b"\x00" * 12).decode(),
        },
    )
    assert resp.status_code == 413
