"""加密 + key 编/解码单元测试。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 把 mcp-server 加到 sys.path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "mcp-server" / "src"))

from agent_handoff_mcp import crypto, key  # noqa: E402


def test_key_roundtrip() -> None:
    hk, bundle_id, enc_key = key.make_handoff_key()
    assert hk.startswith("ah-")
    assert "." in hk
    assert len(bundle_id) == 32
    assert len(enc_key) == 32

    parsed_id, parsed_key = key.parse_handoff_key(hk)
    assert parsed_id == bundle_id
    assert parsed_key == enc_key


def test_invalid_key() -> None:
    with pytest.raises(ValueError):
        key.parse_handoff_key("not-a-key")
    with pytest.raises(ValueError):
        key.parse_handoff_key("ah-onlytheidpart")
    with pytest.raises(ValueError):
        key.parse_handoff_key("ah-7f3a9b2c8e1d4f5a6b7c8d9e0f1a2b3c.tooshortkey")


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = b"hello world, \xe4\xb8\xad\xe6\x96\x87"  # 含中文
    enc_key = crypto.key_from_b64(crypto.new_key_b64())
    bundle_id = "7f3a9b2c8e1d4f5a6b7c8d9e0f1a2b3c"
    aad = bundle_id.encode("utf-8")

    ct, nonce = crypto.encrypt(plaintext, enc_key, aad)
    assert len(nonce) == 12
    assert len(ct) > len(plaintext)  # 包含 16 字节 tag

    recovered = crypto.decrypt(ct, enc_key, nonce, aad)
    assert recovered == plaintext


def test_aad_mismatch_raises() -> None:
    """换 AAD 应该解密失败(防密文替换)。"""
    plaintext = b"important data"
    enc_key = crypto.key_from_b64(crypto.new_key_b64())
    ct, nonce = crypto.encrypt(plaintext, enc_key, b"bundle-A")
    with pytest.raises(Exception):  # cryptography.exceptions.InvalidTag
        crypto.decrypt(ct, enc_key, nonce, b"bundle-B")


def test_wrong_key_raises() -> None:
    plaintext = b"x"
    k1 = crypto.key_from_b64(crypto.new_key_b64())
    k2 = crypto.key_from_b64(crypto.new_key_b64())
    ct, nonce = crypto.encrypt(plaintext, k1, b"x")
    with pytest.raises(Exception):
        crypto.decrypt(ct, k2, nonce, b"x")


def test_nonce_length_validation() -> None:
    with pytest.raises(ValueError):
        crypto.nonce_from_b64(crypto.new_key_b64())  # 32 字节,不是 12


def test_e2e_handoff_key_format() -> None:
    """handoff_key 必须是 URL-safe base64 字符(无 padding)。"""
    hk, _bid, _k = key.make_handoff_key()
    # 32 字节 -> 43 字符 URL-safe base64
    key_part = hk.split(".", 1)[1]
    assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for c in key_part)
    assert "=" not in key_part
