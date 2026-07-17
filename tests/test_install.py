"""install 路由测试。"""
from __future__ import annotations

import base64
import os
import subprocess
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

    tmp = Path(tempfile.mkdtemp(prefix="install-test-"))
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["LOCAL_STORAGE_DIR"] = str(tmp / "bundles")
    os.environ["LOCAL_INDEX_DB"] = str(tmp / "index.sqlite")
    _cfg.get_settings.cache_clear()

    from app.main import create_app  # noqa: E402

    app = create_app()
    with TestClient(app) as c:
        yield c, tmp
    _cfg.get_settings.cache_clear()


def test_install_endpoint_returns_shellscript(client) -> None:
    c, _tmp = client
    r = c.get("/install")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/x-shellscript"
    body = r.text
    assert body.startswith("#!/usr/bin/env bash")
    assert "agent-handoff" in body
    assert "base64 -d" in body
    assert "SKILL.md" in body
    assert "handoff.py" in body


def test_install_uses_query_param_server(client) -> None:
    c, _tmp = client
    r = c.get("/install?server=https://my-host.example.com:9999")
    assert r.status_code == 200
    assert "https://my-host.example.com:9999" in r.text


def test_install_uses_forwarded_headers(client) -> None:
    c, _tmp = client
    r = c.get(
        "/install",
        headers={
            "x-forwarded-proto": "https",
            "x-forwarded-host": "handoff.example.com",
        },
    )
    assert r.status_code == 200
    assert "https://handoff.example.com" in r.text


def test_install_script_actually_runs(client) -> None:
    """端到端: 拉 install 脚本 -> 跑 -> 验证装出文件。"""
    c, _tmp = client
    r = c.get("/install?server=https://test.example.com:8080")
    assert r.status_code == 200
    script = r.text

    fake_home = Path(tempfile.mkdtemp(prefix="install-fake-home-"))
    script_path = fake_home / "install.sh"
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    proc = subprocess.run(
        ["bash", str(script_path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    # 安装可能因为 server 健康检查 fail,但 skill 文件应该装好
    install_dir = fake_home / ".handoff"
    assert (install_dir / "SKILL.md").exists()
    assert (install_dir / "handoff.py").exists()
    assert (install_dir / "handoff").exists()
    config = (install_dir / "config").read_text()
    assert "server_url=https://test.example.com:8080" in config


def test_install_embeds_decodable_skill_md(client) -> None:
    """base64 嵌入的 SKILL.md 应该能被 base64 -d 解码回原内容。"""
    c, _tmp = client
    r = c.get("/install")
    body = r.text
    # 找到 SKILL.md 嵌入的 base64
    # 它在 `printf '%s' 'XXX' | base64 -d > "$INSTALL_DIR/SKILL.md"` 那一行
    import re

    m = re.search(r"printf '%s' '([^']+)' \| base64 -d > \"\$INSTALL_DIR/SKILL\.md\"", body)
    assert m, "找不到 SKILL.md 的 base64 嵌入行"
    b64_str = m.group(1)
    decoded = base64.b64decode(b64_str).decode("utf-8")
    assert "agent-handoff" in decoded.lower() or "handoff" in decoded.lower()
