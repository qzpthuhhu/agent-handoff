#!/usr/bin/env python3
"""端到端演示:A 端打包 → 上传 → B 端拉取 → 验证还原。

不需要起外部 server,直接用 TestClient 跑 FastAPI + MockTransport 桥接 packager/fetcher。
跑法:`python examples/e2e_demo.py`
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mcp-server" / "src"))
sys.path.insert(0, str(_ROOT / "server"))

# 临时配置(必须先 import 之前)
_TMP = Path(tempfile.mkdtemp(prefix="handoff-demo-"))
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_DIR"] = str(_TMP / "bundles")
os.environ["LOCAL_INDEX_DB"] = str(_TMP / "index.sqlite")

import httpx  # noqa: E402

import app.config as _cfg  # noqa: E402

_cfg.get_settings.cache_clear()

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from agent_handoff_mcp import fetcher, packager  # noqa: E402


def main() -> int:
    print("=" * 60)
    print("agent-handoff 端到端演示")
    print("=" * 60)
    print()

    # ====== 0. 准备源文件 ======
    workdir = _TMP / "demo"
    workdir.mkdir()
    src_file = workdir / "report.md"
    src_file.write_text(
        "# Q3 2026 财报摘要\n\n"
        "- 总营收: $42M (+20% YoY)\n"
        "- 毛利: 68%\n"
        "- 重点产品: Helix, Comet\n",
        encoding="utf-8",
    )
    print(f"📁 源文件: {src_file}")
    print(f"   内容: {src_file.read_text(encoding='utf-8')[:50]}...")
    print()

    # ====== 1. 启动 server(用 TestClient + MockTransport) ======
    app = create_app()
    with TestClient(app) as client:
        # 桥接 packager/fetcher 内部 httpx.post/get → TestClient
        orig_post = httpx.post
        orig_get = httpx.get

        def _patched_post(url, **kw):
            return client.post(url, **kw)

        def _patched_get(url, **kw):
            return client.get(url, **kw)

        httpx.post = _patched_post
        httpx.get = _patched_get

        try:
            run_demo(client, src_file, workdir, _TMP, os.environ["LOCAL_STORAGE_DIR"])
        finally:
            httpx.post = orig_post
            httpx.get = orig_get
    return 0


def run_demo(
    client: TestClient,
    src_file: Path,
    workdir: Path,
    tmp_root: Path,
    storage_dir: str,
) -> None:
    print("🚀 启动 handoff server(in-process,本地文件系统后端)")

    health = client.get("/api/v1/health").json()
    print(f"   health: {health}")
    print()

    # ====== 2. A 端打包 + 上传 ======
    print("=" * 60)
    print("📤 A 端:打包对话 + 加密 + 上传")
    print("=" * 60)
    messages = [
        {
            "role": "user",
            "content": "帮我看一下 Q3 财报,做一份摘要",
            "ts": "2026-07-17T15:00:00Z",
        },
        {
            "role": "assistant",
            "content": "好的,先打开 report.md ...",
            "ts": "2026-07-17T15:00:05Z",
        },
        {
            "role": "assistant",
            "content": "摘要:总营收 $42M,+20% YoY,毛利 68%。重点产品是 Helix 和 Comet。",
            "ts": "2026-07-17T15:00:30Z",
            "tool_calls": [{"name": "read_file", "input": {"path": str(src_file)}}],
        },
        {
            "role": "user",
            "content": "ok,把这份上下文 handoff 给 B,让它接着做下季度规划",
            "ts": "2026-07-17T15:01:00Z",
        },
    ]

    server_url = "http://demo"  # MockTransport 不解析 host
    result = packager.package_and_upload(
        messages=messages,
        server_url=server_url,
        files=[str(src_file)],
        metadata={"topic": "Q3 review handoff"},
        hint="from A to B",
        source={"client": "demo", "user": "alice"},
    )
    handoff_key = result["handoff_key"]
    print()
    print("✅ 上传成功!")
    print()
    print("📋 handoff_key:")
    print(f"   {handoff_key}")
    print()
    print(f"   bundle_id: {result['bundle_id']}")
    print(f"   消息数: {result['n_messages']}")
    print(f"   文件数: {result['n_files']}")
    print(f"   密文大小: {result['size']} bytes")
    print(f"   过期: {result['expires_at']}")
    print()

    # ====== 3. 模拟人肉传递 ======
    print("=" * 60)
    print("👤 用户复制 handoff_key,粘到 B 端")
    print("=" * 60)
    print(f"   >>> [复制到剪贴板] {handoff_key[:30]}...{handoff_key[-10:]}")
    print()

    # ====== 4. B 端拉取 + 解密 + 落盘 ======
    print("=" * 60)
    print("📥 B 端:拉取 + 解密 + 落盘")
    print("=" * 60)
    output_dir = workdir / "handoff-out"
    summary = fetcher.fetch_and_decrypt(
        handoff_key=handoff_key,
        server_url=server_url,
        output_dir=str(output_dir),
    )
    print()
    print("✅ 拉取成功!")
    print()
    print(f"   落地目录: {summary['output_dir']}")
    print(f"   元数据:   {summary['metadata']}")
    print(f"   消息:     {summary['messages']} ({summary['n_messages']} 条)")
    print(f"   文件数:   {summary['n_files']}")
    for f in summary["files"]:
        print(f"     - {f}")
    print()

    # ====== 5. 验证内容还原 ======
    print("=" * 60)
    print("🔍 验证内容还原")
    print("=" * 60)

    msgs = []
    with open(summary["messages"], encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                msgs.append(json.loads(line))
    print(f"\n📝 还原后的对话({len(msgs)} 条):")
    for m in msgs:
        role = m["role"]
        content = m["content"][:60].replace("\n", " ")
        print(f"  [{role}] {content}{'...' if len(m['content']) > 60 else ''}")

    restored = Path(summary["files"][0])
    same = restored.read_text(encoding="utf-8") == src_file.read_text(encoding="utf-8")
    print(f"\n📄 文件还原正确: {same}")
    print(f"   源 : {src_file}")
    print(f"   目标: {restored}")

    meta = json.loads(Path(summary["metadata"]).read_text(encoding="utf-8"))
    print(f"\n📦 元数据: {json.dumps(meta, ensure_ascii=False, indent=2)}")
    print()

    # ====== 6. 展示服务端存的密文(不暴露明文) ======
    print("=" * 60)
    print("🛡️  服务端存的:仅密文 + 索引,看不到明文")
    print("=" * 60)
    bundle_file = next(Path(storage_dir).glob("*.bin"))
    head = bundle_file.read_text(encoding="utf-8")[:80]
    print(f"\n   {bundle_file.name} (前 80 字符):")
    print(f"   {head!r}")
    print(f"\n   ✓ 服务端只看到 base64 密文,无法还原消息内容")
    print(f"   ✓ key 只在 A、B 两端,没有传到服务端")
    print()

    # ====== 收尾 ======
    print("=" * 60)
    print("🎉 演示完成")
    print("=" * 60)
    print()
    print(f"工作目录: {tmp_root}")
    print("  - A 端源文件在:", src_file.parent)
    print("  - B 端还原在:", output_dir)
    print("  - 服务端密文在:", storage_dir)
    print()
    print("💡 想清理: rm -rf", tmp_root)


if __name__ == "__main__":
    sys.exit(main())
