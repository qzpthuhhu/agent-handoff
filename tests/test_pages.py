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
    """主页应包含显眼的 '复制给 agent' hero 按钮(无 install 模式)。"""
    c, _ = client
    r = c.get("/")
    body = r.text
    # 主 CTA(无 install)+ legacy CTA
    assert "复制纯 curl 接入指令" in body
    assert 'class="cta"' in body
    assert 'class="cta-secondary"' in body
    assert "data-copy=" in body
    # 强调"无 install"
    assert "不需要 install" in body or "无需 install" in body
    # 应该提到 curl 拉 skill.md
    assert "skill.md" in body
    assert "curl" in body.lower()
    # legacy 应被标为不推荐
    assert "legacy" in body.lower() or "审计" in body


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
    # 新版 SKILL.md 是自包含的:含 handoff() / fetch() Python helper
    assert "def handoff" in body
    assert "def fetch" in body
    assert "cryptography" in body
    assert "AES-256-GCM" in body or "AESGCM" in body
    assert "AAD" in body or "aad" in body or "bundle_id" in body
    # 不应该有 base64 嵌入的二进制(避免触发混淆警报)
    # 检查: SKILL.md 不应包含超长 base64 块
    import re
    long_b64 = re.findall(r"[A-Za-z0-9+/=]{200,}", body)
    assert not long_b64, f"SKILL.md 不应包含长 base64 字符串: {len(long_b64)} 个"


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
