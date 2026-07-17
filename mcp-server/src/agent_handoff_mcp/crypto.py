"""AES-256-GCM 加密/解密,严格按 protocol.md 第 4 节。

- Key: 32 字节随机
- Nonce: 12 字节随机,每次加密重新生成
- AAD: bundle_id(把密文和 key 绑死,防止密文在不同 bundle 间被替换)
- 输出: ciphertext || tag(16 字节,GCM 自带)
"""
from __future__ import annotations

import base64
import os
import secrets


def new_key_b64() -> str:
    """生成 32 字节随机 key,返回 URL-safe base64(无 padding)。"""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")


def key_from_b64(s: str) -> bytes:
    """从 URL-safe base64 还原 32 字节 key。"""
    # 补 padding
    pad = "=" * (-len(s) % 4)
    raw = base64.urlsafe_b64decode(s + pad)
    if len(raw) != 32:
        raise ValueError(f"key 长度不对,期望 32 字节,实际 {len(raw)}")
    return raw


def new_nonce_b64() -> str:
    """生成 12 字节随机 nonce,返回 base64。"""
    return base64.b64encode(secrets.token_bytes(12)).decode("ascii")


def nonce_from_b64(s: str) -> bytes:
    raw = base64.b64decode(s, validate=True)
    if len(raw) != 12:
        raise ValueError(f"nonce 长度不对,期望 12 字节,实际 {len(raw)}")
    return raw


def encrypt(plaintext: bytes, key: bytes, aad: bytes) -> tuple[bytes, bytes]:
    """AES-256-GCM 加密。返回 (ciphertext_with_tag, nonce)。"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext, aad)
    return ct, nonce


def decrypt(ciphertext: bytes, key: bytes, nonce: bytes, aad: bytes) -> bytes:
    """AES-256-GCM 解密(失败抛 InvalidTag)。"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, aad)
