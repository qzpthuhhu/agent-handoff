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
        "agent-handoff 把当前 agent 的对话上下文 + 文件加密传给另一个 agent。\n\n"
        "**用户原话 → 怎么调(关键映射)**:\n"
        '- "把刚刚对话的 XXX 主题的记录打包" → 你自己从当前对话历史里挑出跟 XXX 主题相关的轮次,'
        "作为 messages 传进来(可省略 ts,加 role + content 即可),调 package_chat_history\n"
        '- "把前 N 轮对话打包" → 抽最近 N 条 user/assistant 消息\n'
        '- "把前两天对话的 XXX 主题的记录和文件打包,给我 key" → messages 自己抽,files 列出来\n'
        '- "把刚才 / 之前 / 全部 / 某主题 的对话交给另一个 agent" → 抽对应 messages 调 package_chat_history\n\n'
        "**两个工具**:\n"
        "- `package_chat_history(messages, server_url, ...)` — A 端用,返回 handoff key 给用户复制\n"
        "- `fetch_chat_history(handoff_key, server_url, ...)` — B 端用,粘贴 key 后拉取\n"
        "- `inspect_handoff_key(handoff_key)` — 校验 key 格式\n\n"
        "**重要**:\n"
        "1. `messages` 字段你必须自己从你跟用户的对话历史里构造(按主题过滤,挑相关轮次),工具读不到你的 context\n"
        "2. `files` 字段如果你之前读过/写过的文件用户也想要,把它路径列出来\n"
        "3. `server_url` 用户没给的话,问用户或者从历史对话里找\n"
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
    """把对话 + 文件加密打包,返回 handoff key(给 B 端用)。

    **你的工作**:从你跟用户当前的对话历史里抽出 messages(按用户提到的主题过滤,挑相关轮次)。
    工具读不到你的 context,所以你必须自己构造 messages 数组。

    常见抽取方式:
    - "刚刚的对话" → 抽最近 5-10 条 user/assistant 消息
    - "前 N 轮" → 抽最近 N 条
    - "XXX 主题相关的" → 挑跟 XXX 主题相关的(可能不是连续的)
    - "全部对话" → 抽整段对话历史
    - "前两天对话" → 如果历史里能找到时间戳,挑时间范围

    参数:
      - messages: messages 数组,每条 {role, content, ts?},role ∈ user/assistant/system/tool。
        必填,至少 1 条,默认 10 条左右。**你必须自己从对话历史里挑**。
      - server_url: handoff server URL,例如 https://aishangai.shop
        必填,问用户或从历史里找
      - files: 文件路径列表(可选),例如 ["/path/to/report.md"]
        用户说"和文件一起打包"时填
      - metadata: 附加元数据(可选),例如 {"topic": "Q3 review"}
        用户说主题时填,方便接收方理解
      - hint: 给接收方的简短备注(可选),例如 "Q3 财报摘要 handoff"
      - expires_in: 过期秒数(可选),默认 7 天,最大 30 天

    返回:handoff_key(用户复制)+ 摘要(n_messages / n_files / expires_at)

    **调用例子**(LLM 看这里照做):

    用户说 "把刚刚对话的 财务主题 打包给另一个 agent":
        messages = 你从对话历史里挑出跟"财务"相关的轮次
        hint = "财务相关对话"
        调:
            package_chat_history(
                messages=[{"role": "user", "content": "..."}, ...],
                server_url="https://aishangai.shop",
                hint="财务相关对话"
            )

    用户说 "把刚才读过的 report.md 也一起打包,前 5 轮":
        messages = 最近 5 条 user/assistant
        files = ["/path/to/report.md"]
        调:
            package_chat_history(
                messages=[...5 条...],
                server_url="https://aishangai.shop",
                files=["/path/to/report.md"],
                hint="前 5 轮 + report.md"
            )
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
