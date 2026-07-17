"""agent-handoff Skill 的 Python CLI 工具。

子命令:
  package  打包 + 加密 + 上传
  fetch    拉取 + 解密 + 落盘
  inspect  校验 handoff key
  server   启动本地 handoff server(开发用)

这个 CLI 复用了 mcp-server 的 packager/fetcher,只做了 CLI 入口。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

# 把同仓的 mcp-server 当库用,避免代码重复
_HERE = Path(__file__).resolve().parent
_MCP_SRC = _HERE.parent.parent.parent / "mcp-server" / "src"
if str(_MCP_SRC) not in sys.path:
    sys.path.insert(0, str(_MCP_SRC))

from agent_handoff_mcp import fetcher, packager  # noqa: E402


def cmd_package(args: argparse.Namespace) -> int:
    messages: list[dict]
    if args.messages_json:
        messages = json.loads(Path(args.messages_json).read_text(encoding="utf-8"))
    elif args.messages:
        messages = json.loads(args.messages)
    else:
        print("❌ 必须通过 --messages-json 或 --messages 提供 messages", file=sys.stderr)
        return 2

    files = None
    if args.files:
        files = [f.strip() for f in args.files.split(",") if f.strip()]

    metadata = None
    if args.metadata:
        metadata = json.loads(args.metadata)

    server_url = args.server_url or os.environ.get("HANDOFF_SERVER_URL")
    if not server_url:
        print("❌ 必须通过 --server-url 或 HANDOFF_SERVER_URL 提供 server URL", file=sys.stderr)
        return 2

    try:
        result = packager.package_and_upload(
            messages=messages,
            server_url=server_url,
            files=files,
            metadata=metadata,
            hint=args.hint,
            expires_in=args.expires_in,
        )
    except packager.PackageError as e:
        print(f"❌ 打包失败: {e}", file=sys.stderr)
        return 1

    print("✅ 上传成功!")
    print()
    print("📋 handoff_key(复制给接收方):")
    print(f"  {result['handoff_key']}")
    print()
    print(f"  bundle_id : {result['bundle_id']}")
    print(f"  消息数     : {result['n_messages']}")
    print(f"  文件数     : {result['n_files']}")
    print(f"  密文大小   : {result['size']} bytes")
    print(f"  过期时间   : {result['expires_at']}")
    print()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    server_url = args.server_url or os.environ.get("HANDOFF_SERVER_URL")
    if not server_url:
        print("❌ 必须通过 --server-url 或 HANDOFF_SERVER_URL 提供 server URL", file=sys.stderr)
        return 2
    try:
        summary = fetcher.fetch_and_decrypt(
            handoff_key=args.handoff_key,
            server_url=server_url,
            output_dir=args.output_dir,
        )
    except fetcher.FetchError as e:
        print(f"❌ 拉取失败: {e}", file=sys.stderr)
        return 1
    print("✅ 拉取成功!")
    print()
    print(f"  落地目录 : {summary['output_dir']}")
    print(f"  元数据   : {summary['metadata']}")
    print(f"  消息     : {summary['messages']} ({summary['n_messages']} 条)")
    print(f"  文件数   : {summary['n_files']}")
    if summary.get("files"):
        print("  文件列表:")
        for f in summary["files"]:
            print(f"    - {f}")
    print()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    from agent_handoff_mcp.key import parse_handoff_key  # noqa: E402

    try:
        bundle_id, enc_key = parse_handoff_key(args.handoff_key)
    except Exception as e:
        print(f"❌ key 不合法: {e}", file=sys.stderr)
        return 1
    print("✅ key 格式合法")
    print(f"  bundle_id : {bundle_id}")
    print(f"  enc_key   : {len(enc_key)} bytes (AES-256)")
    return 0


def cmd_server(args: argparse.Namespace) -> int:
    """启动本地 handoff server(开发用)。"""
    import subprocess

    server_dir = _HERE.parent.parent / "server"
    if not (server_dir / "app" / "main.py").exists():
        print(f"❌ 找不到 server 入口: {server_dir / 'app/main.py'}", file=sys.stderr)
        return 1
    env = os.environ.copy()
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    print(f"启动 server: {' '.join(cmd)} (cwd={server_dir})", file=sys.stderr)
    return subprocess.call(cmd, cwd=str(server_dir), env=env)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="handoff",
        description="agent-handoff CLI: 跨 agent 加密传输聊天记录和文件",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # package
    pp = sub.add_parser("package", help="打包 + 加密 + 上传")
    pp.add_argument("--server-url", help="handoff server URL(或 env HANDOFF_SERVER_URL)")
    pp.add_argument("--messages-json", help="messages JSON 文件路径")
    pp.add_argument("--messages", help="messages JSON 字符串")
    pp.add_argument("--files", help="逗号分隔的文件路径列表")
    pp.add_argument("--metadata", help="metadata JSON 字符串")
    pp.add_argument("--hint", help="备注")
    pp.add_argument("--expires-in", type=int, help="过期秒数")
    pp.set_defaults(func=cmd_package)

    # fetch
    pf = sub.add_parser("fetch", help="拉取 + 解密 + 落盘")
    pf.add_argument("--handoff-key", required=True, help="ah-{id}.{key}")
    pf.add_argument("--server-url", help="handoff server URL")
    pf.add_argument("--output-dir", help="落地目录")
    pf.set_defaults(func=cmd_fetch)

    # inspect
    pi = sub.add_parser("inspect", help="校验 handoff key 格式")
    pi.add_argument("--handoff-key", required=True)
    pi.set_defaults(func=cmd_inspect)

    # server
    ps = sub.add_parser("server", help="启动本地 handoff server(开发用)")
    ps.add_argument("--host", default="0.0.0.0")
    ps.add_argument("--port", type=int, default=8080)
    ps.set_defaults(func=cmd_server)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
