"""MCP Server 入口:暴露 package 和 fetch 两个工具。

在支持 MCP 的 agent 里(Claude Desktop / Cursor / Cline / 自研)注册后,LLM 可以直接调用。
"""
from __future__ import annotations

import json
import os
import socket
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .fetcher import FetchError, fetch_and_decrypt
from .key import parse_handoff_key
from .packager import PackageError, package_and_upload

mcp = FastMCP(
    "agent-handoff",
    instructions=(
        "在 A agent 端用 `package_chat_history` 把最近的对话 + 文件打包, "
        "得到一个 handoff key(用户复制给 B)。在 B agent 端用 `fetch_chat_history` "
        "粘贴 key + server URL 拉取,消息和文件会解密到本地目录。"
    ),
)


def _default_source() -> dict:
    """猜测一下源 agent(尽力而为,不重要)。"""
    return {
        "client": os.environ.get("HANDOFF_CLIENT", "mcp"),
        "user": os.environ.get("USER") or os.environ.get("USERNAME") or "",
        "host": socket.gethostname(),
    }


@mcp.tool()
def package_chat_history(
    messages: list[dict],
    server_url: str,
    files: Optional[list[str]] = None,
    metadata: Optional[dict] = None,
    hint: Optional[str] = None,
    expires_in: Optional[int] = None,
) -> str:
    """打包最近的聊天记录 + 过程文件,加密后上传到 handoff server,返回 handoff key。

    参数:
      - messages: 最近的聊天记录数组,每条 {role, content, ts?}。
        重要:把"前 N 轮"的完整内容传进来,工具不读取 LLM 上下文。
      - server_url: handoff server 地址,例如 https://handoff.example.com
      - files: 要一并传输的本地文件路径列表(可选)
      - metadata: 附加元数据,例如 {"topic": "Q3 review"} (可选)
      - hint: 给接收方的简短备注(可选,显示在服务端)
      - expires_in: 过期秒数,默认 7 天,最大 30 天(可选)

    返回(人类可读 + JSON 双行):
      handoff_key: 用户复制,粘到 B agent
      n_messages / n_files / expires_at: 摘要
    """
    try:
        result = package_and_upload(
            messages=messages,
            server_url=server_url,
            files=files or None,
            metadata=metadata,
            source=_default_source(),
            hint=hint,
            expires_in=expires_in,
        )
    except PackageError as e:
        return f"❌ 打包失败: {e}"

    key = result["handoff_key"]
    return (
        "✅ 上传成功!\n\n"
        f"📋 **handoff_key**(复制给接收方):\n```\n{key}\n```\n\n"
        f"- bundle_id: `{result['bundle_id']}`\n"
        f"- 消息数: {result['n_messages']}\n"
        f"- 文件数: {result['n_files']}\n"
        f"- 密文大小: {result['size']} bytes\n"
        f"- 过期时间: {result['expires_at']}\n\n"
        "接收方调用 `fetch_chat_history(handoff_key=..., server_url=...)` 即可拉取。"
        + "\n\n" + json.dumps(result, ensure_ascii=False, indent=2)
    )


@mcp.tool()
def fetch_chat_history(
    handoff_key: str,
    server_url: str,
    output_dir: Optional[str] = None,
) -> str:
    """从 handoff server 拉取并解密一个 bundle,落盘到本地目录。

    参数:
      - handoff_key: 发送方给的 handoff key(ah-xxx.yyy)
      - server_url: handoff server 地址
      - output_dir: 解密落地目录,默认 ./handoff/{bundle_id}-{ts}

    返回:
      - output_dir: 落盘的目录
      - messages: 消息 jsonl 路径
      - files: 还原的文件路径列表
      - n_messages / n_files: 数量
    """
    try:
        summary = fetch_and_decrypt(
            handoff_key=handoff_key,
            server_url=server_url,
            output_dir=output_dir,
        )
    except FetchError as e:
        return f"❌ 拉取失败: {e}"

    return (
        "✅ 拉取成功!\n\n"
        f"- 落地目录: `{summary['output_dir']}`\n"
        f"- 元数据: `{summary['metadata']}`\n"
        f"- 消息: `{summary['messages']}` ({summary['n_messages']} 条)\n"
        f"- 文件数: {summary['n_files']}\n"
        + (
            f"- 文件列表:\n"
            + "\n".join(f"  - `{f}`" for f in summary["files"])
            if summary["files"]
            else ""
        )
        + "\n\n你可以读取 messages.jsonl 接着上文,或直接引用 files/ 下的文件。"
        + "\n\n" + json.dumps(summary, ensure_ascii=False, indent=2)
    )


@mcp.tool()
def inspect_handoff_key(handoff_key: str) -> str:
    """检查 handoff key 格式是否合法(不实际拉取)。"""
    try:
        bundle_id, enc_key = parse_handoff_key(handoff_key)
    except Exception as e:
        return f"❌ key 不合法: {e}"
    return (
        "✅ key 格式合法\n\n"
        f"- bundle_id: `{bundle_id}` (length={len(bundle_id)})\n"
        f"- enc_key: {len(enc_key)} bytes (AES-256)"
    )


if __name__ == "__main__":
    mcp.run()
