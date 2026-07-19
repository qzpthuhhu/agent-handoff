"""页面路由测试(主页 / agents.txt / skill.md / guide.md)。"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "server"))


@pytest.fixture
def client():
    import app.config as _cfg  # noqa: E402
    from fastapi.testclient import TestClient  # noqa: E402

    tmp = Path(tempfile.mkdtemp(prefix="pages-test-"))
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp / "bundles")
    os.environ["LOCAL_INDEX_DB"] = str(tmp / "index.sqlite")
    _cfg.get_settings.cache_clear()

    from app.main import create_app  # noqa: E402

    app = create_app()
    with TestClient(app) as c:
        yield c, tmp
    _cfg.get_settings.cache_clear()


def test_home_returns_html(client) -> None:
    c, _ = client
    r = c.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text
    assert "agent-handoff" in body
    assert "三步搞定" in body
    assert "package_chat_history" in body
    assert "fetch_chat_history" in body
    assert "/install" in body
    assert "/guide.md" in body


def test_home_has_hero_cta(client) -> None:
    """主页应包含显眼的 '复制给 agent' hero 按钮 + SHA256 + 一键版。"""
    c, _ = client
    r = c.get("/")
    body = r.text
    # 审计版 + 一键版 hero CTA
    assert "复制审计版指令" in body
    assert "class=\"cta\"" in body
    assert "class=\"cta-secondary\"" in body
    assert "data-copy=" in body
    # 内容应该包括审计步骤
    assert "install" in body.lower()
    assert "fetch" in body.lower()
    assert "messages.jsonl" in body or "files/" in body
    # SHA256 占位符
    assert "__INSTALL_SHA256__" in body or "install-sha" in body


def test_install_endpoint_returns_sha256_header(client) -> None:
    """/install 应该返回 X-Handoff-SHA256 header,让客户端验证完整性。"""
    c, _ = client
    r = c.get("/install")
    assert r.status_code == 200
    sha = r.headers.get("X-Handoff-SHA256")
    assert sha is not None
    assert len(sha) == 64  # SHA-256 hex length
    import hashlib
    expected = hashlib.sha256(r.text.encode("utf-8")).hexdigest()
    assert sha == expected


def test_home_has_copy_buttons(client) -> None:
    """每个 pre code 旁边应有复制按钮 + JS 函数。"""
    c, _ = client
    r = c.get("/")
    body = r.text
    # 复制按钮
    assert body.count('class="copy-btn"') >= 1
    # JS 函数
    assert "function copyText" in body
    assert "navigator.clipboard" in body
    # pre 块
    assert "<pre>" in body


def test_home_includes_clipboard_fallback(client) -> None:
    """即使是非安全上下文(navigator.clipboard 不可用)也应该能复制。"""
    c, _ = client
    r = c.get("/")
    body = r.text
    assert "execCommand" in body  # 旧浏览器 fallback
    assert "document.createElement" in body


def test_agents_txt(client) -> None:
    c, _ = client
    r = c.get("/agents.txt")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    body = r.text
    assert "User-Agent: *" in body
    assert "Allow: /" in body
    assert "/guide.md" in body
    assert "/skill.md" in body
    assert "/install" in body


def test_skill_md(client) -> None:
    c, _ = client
    r = c.get("/skill.md")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    body = r.text
    assert "agent-handoff" in body
    assert "package" in body
    assert "fetch" in body
    assert "inspect" in body


def test_guide_md(client) -> None:
    c, _ = client
    r = c.get("/guide.md")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    body = r.text
    assert "User intent" in body
    assert "package_chat_history" in body
    assert "fetch_chat_history" in body
    assert "E2E" in body or "end-to-end" in body.lower()
    assert "AES-256-GCM" in body


def test_pages_dont_leak_secrets(client) -> None:
    """页面不应该泄露 .env 里的 ADMIN_TOKEN 等敏感信息。"""
    c, _ = client
    for path in ["/", "/guide.md", "/skill.md", "/agents.txt", "/install"]:
        r = c.get(path)
        assert r.status_code in (200,)
        # 简单检查:不应包含 'admin_token' 之类的字段
        assert "ADMIN_TOKEN" not in r.text
        assert "secret_key" not in r.text.lower()
