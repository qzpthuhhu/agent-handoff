"""Handoff key 编/解码。

格式:`ah-{bundle_id}.{enc_key_b64}`
"""
from __future__ import annotations

import re
import secrets

from .crypto import key_from_b64, new_key_b64

# 32 字节 hex = 64 字符,但 protocol 里只要求 32 字符(16 字节)。
# 我们用 16 字节 hex 长度(32 字符),足够防撞库。
_ID_RE = re.compile(r"^ah-([0-9a-f]+)\.([A-Za-z0-9_-]+)$")


def new_bundle_id(nbytes: int = 16) -> str:
    """生成 16 字节 hex bundle id(32 字符)。"""
    return secrets.token_hex(nbytes)


def make_handoff_key(bundle_id: str | None = None) -> tuple[str, str, bytes]:
    """生成 (handoff_key, bundle_id, enc_key_bytes)。

    - handoff_key: 用户复制的字符串
    - bundle_id: 32 字符 hex
    - enc_key_bytes: 32 字节,后续加密用
    """
    if bundle_id is None:
        bundle_id = new_bundle_id()
    enc_key_b64 = new_key_b64()
    handoff_key = f"ah-{bundle_id}.{enc_key_b64}"
    return handoff_key, bundle_id, key_from_b64(enc_key_b64)


def parse_handoff_key(handoff_key: str) -> tuple[str, bytes]:
    """解析 handoff_key → (bundle_id, enc_key_bytes)。失败抛 ValueError。"""
    m = _ID_RE.match(handoff_key.strip())
    if not m:
        raise ValueError(f"handoff_key 格式不合法: {handoff_key[:60]!r}")
    bundle_id, enc_key_b64 = m.group(1), m.group(2)
    return bundle_id, key_from_b64(enc_key_b64)
