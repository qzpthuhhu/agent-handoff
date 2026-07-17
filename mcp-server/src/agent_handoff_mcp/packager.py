"""打包:把消息列表 + 文件读取 + 元数据 → 加密 → 上传 → 返回 handoff_key。"""
from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from . import crypto
from .key import make_handoff_key


MAX_FILE_SIZE = 10 * 1024 * 1024  # 单文件 10MB
MAX_TOTAL_FILES_SIZE = 30 * 1024 * 1024  # 总文件 30MB


class PackageError(RuntimeError):
    pass


def _read_file(path: str, max_size: int = MAX_FILE_SIZE) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise PackageError(f"文件不存在: {path}")
    if not p.is_file():
        raise PackageError(f"不是文件: {path}")
    size = p.stat().st_size
    if size > max_size:
        raise PackageError(
            f"文件过大: {path} ({size} bytes, 上限 {max_size} bytes)"
        )
    with open(p, "rb") as f:
        raw = f.read()
    mime, _ = mimetypes.guess_type(str(p))
    return {
        "name": p.name,
        "path": str(p),
        "content_b64": base64.b64encode(raw).decode("ascii"),
        "size": size,
        "mime": mime or "application/octet-stream",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def build_payload(
    messages: list[dict],
    files: Optional[list[str]] = None,
    metadata: Optional[dict] = None,
    source: Optional[dict] = None,
) -> dict:
    """构造明文 payload(protocol § 4)。"""
    return {
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source or {},
        "messages": messages,
        "files": [_read_file(p) for p in (files or [])],
        "metadata": metadata or {},
    }


def encrypt_payload(payload: dict, enc_key: bytes, bundle_id: str) -> tuple[str, str]:
    """加密 payload → (ciphertext_b64, nonce_b64)。"""
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    aad = bundle_id.encode("utf-8")
    ct, nonce = crypto.encrypt(plaintext, enc_key, aad)
    return (
        base64.b64encode(ct).decode("ascii"),
        base64.b64encode(nonce).decode("ascii"),
    )


def upload(
    server_url: str,
    bundle_id: str,
    ciphertext_b64: str,
    nonce_b64: str,
    expires_in: Optional[int] = None,
    hint: Optional[str] = None,
    timeout: float = 30,
) -> dict:
    """POST 到服务端,返回响应 JSON。"""
    url = server_url.rstrip("/") + "/api/v1/bundles"
    body: dict[str, Any] = {
        "id": bundle_id,
        "ciphertext_b64": ciphertext_b64,
        "nonce_b64": nonce_b64,
    }
    if expires_in is not None:
        body["expires_in"] = expires_in
    if hint:
        body["hint"] = hint
    try:
        resp = httpx.post(url, json=body, timeout=timeout)
    except httpx.HTTPError as e:
        raise PackageError(f"上传失败(网络): {e}") from e
    if resp.status_code != 201:
        raise PackageError(f"上传失败(status={resp.status_code}): {resp.text[:300]}")
    return resp.json()


def package_and_upload(
    messages: list[dict],
    server_url: str,
    files: Optional[list[str]] = None,
    metadata: Optional[dict] = None,
    source: Optional[dict] = None,
    hint: Optional[str] = None,
    expires_in: Optional[int] = None,
) -> dict:
    """一站式:打包 + 加密 + 上传。

    返回:
    ```
    {
      "handoff_key": "ah-xxx.yyy",   # 给用户复制
      "bundle_id": "...",
      "size": 12345,
      "expires_at": "2026-...",
      "n_messages": 10,
      "n_files": 3,
    }
    ```
    """
    if not messages:
        raise PackageError("messages 不能为空,至少要传一条")
    if not server_url:
        raise PackageError("server_url 必填")

    payload = build_payload(messages, files=files, metadata=metadata, source=source)
    handoff_key, bundle_id, enc_key = make_handoff_key()
    ciphertext_b64, nonce_b64 = encrypt_payload(payload, enc_key, bundle_id)

    server_resp = upload(
        server_url=server_url,
        bundle_id=bundle_id,
        ciphertext_b64=ciphertext_b64,
        nonce_b64=nonce_b64,
        expires_in=expires_in,
        hint=hint,
    )

    return {
        "handoff_key": handoff_key,
        "bundle_id": bundle_id,
        "size": server_resp.get("size"),
        "expires_at": server_resp.get("expires_at"),
        "n_messages": len(messages),
        "n_files": len(payload["files"]),
    }
