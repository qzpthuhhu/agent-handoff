"""`GET /install` 路由:返回一段 bash 一键安装脚本。

脚本内容由本路由动态生成,会把 server URL + SKILL.md + handoff.py + 整个
mcp-server Python 模块 全部嵌入到一个自包含的 bash 文件里,用户只要:
    curl -fsSL http://server/install | bash
就能把 skill 装到 ~/.handoff/。

支持:
  ?server=https://...   显式指定 server URL
  X-Forwarded-Proto + X-Forwarded-Host(nginx 反代时自动推断)
"""
from __future__ import annotations

import base64
import io
import tarfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query, Request, Response

router = APIRouter(tags=["install"])

# 资产路径(在 Docker 镜像里)
_SKILL_MD_PATH = Path("/install/SKILL.md")
_HANDOFF_PY_PATH = Path("/install/scripts/handoff.py")
_MCP_SRC_PATH = Path("/install/mcp_src")


def _infer_server_url(request: Request, explicit: Optional[str]) -> str:
    """根据 ?server= 参数、nginx header 或者 request URL 推断 server URL。"""
    if explicit:
        return explicit.rstrip("/")
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "localhost:8080")
    return f"{scheme}://{host}"


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _b64_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _pack_mcp_src() -> bytes:
    """把整个 mcp-server 模块打包成 tar.gz bytes(供 base64 嵌入)。"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for f in _MCP_SRC_PATH.iterdir():
            if f.is_file():
                tar.add(str(f), arcname=f"agent_handoff_mcp/{f.name}")
    return buf.getvalue()


@router.get("/install", include_in_schema=False)
def install_script(
    request: Request,
    server: Optional[str] = Query(default=None, description="显式指定 server URL"),
) -> Response:
    server_url = _infer_server_url(request, server)

    if _SKILL_MD_PATH.exists():
        skill_md = _SKILL_MD_PATH.read_text(encoding="utf-8")
    else:
        skill_md = "# agent-handoff\n\nSee server docs.\n"

    if _HANDOFF_PY_PATH.exists():
        handoff_py = _HANDOFF_PY_PATH.read_text(encoding="utf-8")
    else:
        handoff_py = "# handoff.py not found in image\n"

    mcp_tar_b64 = ""
    if _MCP_SRC_PATH.exists() and _MCP_SRC_PATH.is_dir():
        mcp_tar_b64 = _b64_bytes(_pack_mcp_src())

    script = _render_install_script(
        server_url=server_url,
        skill_md=skill_md,
        handoff_py=handoff_py,
        mcp_tar_b64=mcp_tar_b64,
    )

    return Response(
        content=script,
        media_type="application/x-shellscript",
        headers={
            "Content-Disposition": 'inline; filename="install.sh"',
            "Cache-Control": "no-store",
        },
    )


def _render_install_script(
    server_url: str, skill_md: str, handoff_py: str, mcp_tar_b64: str
) -> str:
    """拼出最终 bash 脚本。所有二进制/多行内容都用 base64 嵌入。"""
    skill_b64 = _b64(skill_md)
    handoff_b64 = _b64(handoff_py)

    # mcp tarball 段(可能为空)
    mcp_block = ""
    if mcp_tar_b64:
        mcp_block = f"""
# === 2.5. 写 mcp-server 模块(打包的 tar.gz) ===
printf '%s' '{mcp_tar_b64}' | base64 -d > "$INSTALL_DIR/mcp_src.tar.gz"
mkdir -p "$INSTALL_DIR/lib"
tar -xzf "$INSTALL_DIR/mcp_src.tar.gz" -C "$INSTALL_DIR/lib/"
rm -f "$INSTALL_DIR/mcp_src.tar.gz"
"""

    return f"""#!/usr/bin/env bash
# ============================================================
# agent-handoff 一键安装脚本
# 自动生成于 {server_url}
# 把它 pipe 给 bash:    curl -fsSL {server_url}/install | bash
# ============================================================
set -euo pipefail

# === 0. 取 server URL ===
if [ -n "${{1:-}}" ]; then
  SERVER_URL="$1"
elif [ -n "${{HANDOFF_SERVER_URL:-}}" ]; then
  SERVER_URL="$HANDOFF_SERVER_URL"
else
  SERVER_URL="{server_url}"
fi
INSTALL_DIR="${{HANDOFF_HOME:-$HOME/.handoff}}"

echo "→ 安装到: $INSTALL_DIR"
echo "→ server : $SERVER_URL"
mkdir -p "$INSTALL_DIR"

# === 1. 写 SKILL.md ===
printf '%s' '{skill_b64}' | base64 -d > "$INSTALL_DIR/SKILL.md"

# === 2. 写 handoff.py ===
printf '%s' '{handoff_b64}' | base64 -d > "$INSTALL_DIR/handoff.py"
chmod +x "$INSTALL_DIR/handoff.py"
{mcp_block}
# === 3. 写 config(供后续调用) ===
cat > "$INSTALL_DIR/config" <<EOF
server_url=$SERVER_URL
installed_at=$(date -Iseconds)
EOF

# === 4. 写 thin wrapper(让 PATH 一加就能跑 `handoff`) ===
cat > "$INSTALL_DIR/handoff" <<'WRAP'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
SERVER_URL=$(grep '^server_url=' "$DIR/config" | cut -d= -f2-)
exec python3 "$DIR/handoff.py" --server-url "$SERVER_URL" "$@"
WRAP
chmod +x "$INSTALL_DIR/handoff"

# === 5. 验连通 ===
if command -v curl >/dev/null 2>&1; then
  if curl -fsS --max-time 5 "$SERVER_URL/api/v1/health" >/dev/null 2>&1; then
    echo "✓ server reachable"
  else
    echo "⚠ server 健康检查失败,但 skill 已经装好,稍后手动验证"
  fi
fi

echo ""
echo "============================================================"
echo "✓ agent-handoff skill installed at $INSTALL_DIR"
echo "  server: $SERVER_URL"
echo "  lib   : $INSTALL_DIR/lib/agent_handoff_mcp/ (mcp-server module)"
echo ""
echo "用法:"
echo "  export PATH=\"\\$PATH:$INSTALL_DIR\""
echo "  handoff package --messages-json ./msgs.json --hint 'topic'"
echo "  handoff fetch   --handoff-key ah-xxx.yyy --output-dir ./out"
echo "  handoff inspect --handoff-key ah-xxx.yyy"
echo "  handoff --help"
echo ""
echo "如果别的 agent 第一次接入,在它的对话里贴:"
echo '  "请运行 bash -c \"$(curl -fsSL '"$SERVER_URL"'/install)\" 然后 fetch handoff: ah-..."'
echo "============================================================"
"""
