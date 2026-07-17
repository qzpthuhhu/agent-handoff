#!/usr/bin/env python3
"""一键部署测试:本机起 server,跑真实 HTTP 端到端验证。

用法:
    python examples/deploy_test.py
    # 或者指定端口
    python examples/deploy_test.py --port 18080

流程:
    1. 找空闲端口
    2. 起 uvicorn 子进程(用 .venv 里的 Python)
    3. 等 health 通过
    4. packager 打包 + 上传 → 拿 handoff_key
    5. fetcher 拉取 + 解密 → 落盘
    6. 验证消息/文件完全还原
    7. 验证服务端存的密文不含明文
    8. 关掉 server
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcp-server" / "src"))


def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(port: int, work_dir: Path, venv_python: Path) -> tuple[subprocess.Popen, Path, dict]:
    """起 uvicorn,返回 (proc, log_path, env)。"""
    env = os.environ.copy()
    env["STORAGE_BACKEND"] = "local"
    env["LOCAL_STORAGE_DIR"] = str(work_dir / "bundles")
    env["LOCAL_INDEX_DB"] = str(work_dir / "index.sqlite")
    env["PORT"] = str(port)
    # 不让 .env 干扰(用 env 覆盖)
    env.pop("HOST", None)
    env.pop("LOG_LEVEL", None)

    log_path = work_dir / "server.log"
    log = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            str(venv_python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ],
        cwd=str(ROOT / "server"),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    return proc, log_path, env


def wait_health(url: str, timeout: float = 15) -> bool:
    import httpx

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=1.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0, help="指定端口(0=自动找空闲)")
    parser.add_argument(
        "--keep", action="store_true", help="测试完保留 server(方便手动继续测)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("agent-handoff 一键部署测试")
    print("=" * 60)

    # 找 venv python
    venv_python = ROOT / ".venv" / "bin" / "python"
    if not venv_python.exists():
        print(f"❌ 没找到 .venv,请先: cd {ROOT} && python3 -m venv .venv && "
              f".venv/bin/pip install -r server/requirements.txt")
        return 1

    work_dir = Path(tempfile.mkdtemp(prefix="handoff-deploy-"))
    port = args.port or find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    print(f"\n📁 工作目录: {work_dir}")
    print(f"🌐 监听端口: {port}")
    print(f"🐍 Python  : {venv_python}")

    # 1. 起 server
    print("\n1️⃣  启动 server...")
    proc, log_path, env = start_server(port, work_dir, venv_python)
    print(f"   PID: {proc.pid}, log: {log_path}")

    try:
        if not wait_health(f"{base_url}/api/v1/health"):
            log_content = log_path.read_text(encoding="utf-8")
            print(f"   ❌ server 启动失败,日志:\n{log_content[-1500:]}")
            return 1
        print("   ✓ health OK")

        # 2. 准备测试数据
        print("\n2️⃣  准备测试数据...")
        test_file = work_dir / "demo.txt"
        test_file.write_text(
            "Hello from A to B!\n"
            "机密内容:项目代号 Helix,预算 50M\n"
            "中文测试:传递上下文\n",
            encoding="utf-8",
        )
        messages = [
            {"role": "user", "content": "把上下文传给 B"},
            {"role": "assistant", "content": "好的,正在打包 10 条消息 + 1 个文件..."},
            {"role": "user", "content": "里面那个机密别忘了"},
        ]
        print(f"   ✓ 文件: {test_file.name} ({test_file.stat().st_size} bytes)")
        print(f"   ✓ 消息: {len(messages)} 条")

        # 3. A 端打包
        print("\n3️⃣  A 端:打包 + 加密 + 上传...")
        from agent_handoff_mcp.packager import package_and_upload  # noqa: E402

        result = package_and_upload(
            messages=messages,
            server_url=base_url,
            files=[str(test_file)],
            metadata={"topic": "deploy test"},
            hint="from A",
        )
        handoff_key = result["handoff_key"]
        print(f"   ✓ handoff_key:")
        print(f"     {handoff_key}")
        print(f"   ✓ bundle_id: {result['bundle_id']}")
        print(f"   ✓ size     : {result['size']} bytes")
        print(f"   ✓ 过期     : {result['expires_at']}")

        # 4. B 端拉取
        print("\n4️⃣  B 端:拉取 + 解密 + 落盘...")
        from agent_handoff_mcp.fetcher import fetch_and_decrypt  # noqa: E402

        out_dir = work_dir / "received"
        summary = fetch_and_decrypt(
            handoff_key=handoff_key,
            server_url=base_url,
            output_dir=str(out_dir),
        )
        print(f"   ✓ 落地目录: {summary['output_dir']}")
        print(f"   ✓ 消息数  : {summary['n_messages']}")
        print(f"   ✓ 文件数  : {summary['n_files']}")
        for f in summary["files"]:
            print(f"     - {f}")

        # 5. 验证内容还原
        print("\n5️⃣  验证内容还原...")
        msgs = []
        with open(summary["messages"], encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    msgs.append(json.loads(line))
        assert len(msgs) == 3, f"消息数不匹配: {len(msgs)}"
        assert msgs[0]["content"] == "把上下文传给 B"
        assert msgs[2]["content"] == "里面那个机密别忘了"
        restored = Path(summary["files"][0]).read_text(encoding="utf-8")
        assert "Helix" in restored
        assert "中文测试" in restored
        assert restored == test_file.read_text(encoding="utf-8")
        print("   ✓ 消息内容完全一致")
        print("   ✓ 文件字节级还原(中文/特殊字符都对)")

        # 6. 看密文(确认服务端不存明文)
        print("\n6️⃣  服务端存的密文(看不到明文)...")
        storage_dir = Path(env["LOCAL_STORAGE_DIR"])
        bundle_file = next(storage_dir.glob("*.bin"))
        ciphertext = bundle_file.read_text(encoding="utf-8")
        print(f"   {bundle_file.name}")
        print(f"   {ciphertext[:60]}...")
        assert "Helix" not in ciphertext
        assert "把上下文" not in ciphertext
        assert "中文测试" not in ciphertext
        print("   ✓ 密文里没有 'Helix' / '把上下文' / '中文测试' 等明文关键词")
        print("   ✓ 服务端只能看到 base64 噪声")

        # 7. 测试管理接口(DELETE)
        print("\n7️⃣  测试管理 DELETE(强制删除)...")
        import httpx

        # 没带 admin token → 401
        r = httpx.delete(f"{base_url}/api/v1/bundles/{result['bundle_id']}", timeout=5)
        assert r.status_code == 401
        print("   ✓ 无 token 拒绝(401)")

        # 7. 总结
        print("\n" + "=" * 60)
        print("🎉 部署测试全过!")
        print("=" * 60)
        print(f"\n工作目录: {work_dir}")
        print(f"  server log : {log_path}")
        print(f"  服务端密文 : {storage_dir}")
        print(f"  B 端还原   : {out_dir}")
        if args.keep:
            print(f"\n⏸  Server 保持运行,可以用浏览器访问: {base_url}/api/v1/health")
            print(f"   想关: kill {proc.pid}")
            try:
                proc.wait()
            except KeyboardInterrupt:
                proc.terminate()
        else:
            print(f"\n💡 清理: rm -rf {work_dir}")
        return 0

    finally:
        if not args.keep:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
