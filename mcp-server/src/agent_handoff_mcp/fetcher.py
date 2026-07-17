"""拉取:用 handoff_key 从服务端拿密文,本地解密,落盘。"""
from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from . import crypto
from .key import parse_handoff_key


class FetchError(RuntimeError):
    pass


def fetch_bundle(server_url: str, bundle_id: str, timeout: float = 30) -> dict:
    """GET 服务端,返回密文响应。"""
    url = f"{server_url.rstrip('/')}/api/v1/bundles/{bundle_id}"
    try:
        resp = httpx.get(url, timeout=timeout)
    except httpx.HTTPError as e:
        raise FetchError(f"拉取失败(网络): {e}") from e
    if resp.status_code == 404:
        raise FetchError("bundle 不存在或已过期")
    if resp.status_code == 410:
        raise FetchError("bundle 已过期或被消费")
    if resp.status_code != 200:
        raise FetchError(f"拉取失败(status={resp.status_code}): {resp.text[:300]}")
    return resp.json()


def decrypt_bundle(bundle_id: str, ciphertext_b64: str, nonce_b64: str, enc_key: bytes) -> dict:
    """解密密文 → 明文 payload。"""
    try:
        ct = base64.b64decode(ciphertext_b64, validate=True)
        nonce = crypto.nonce_from_b64(nonce_b64)
    except Exception as e:
        raise FetchError(f"密文格式不合法: {e}") from e
    aad = bundle_id.encode("utf-8")
    try:
        plaintext = crypto.decrypt(ct, enc_key, nonce, aad)
    except Exception as e:
        raise FetchError(f"解密失败(可能 key 错误或密文被篡改): {e}") from e
    try:
        return json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise FetchError(f"明文解析失败: {e}") from e


def write_to_disk(payload: dict, output_dir: Path) -> dict:
    """把 payload 写到 output_dir,返回写入结果摘要。"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # 写元数据
    meta = {
        "version": payload.get("version"),
        "created_at": payload.get("created_at"),
        "source": payload.get("source"),
        "n_messages": len(payload.get("messages", [])),
        "n_files": len(payload.get("files", [])),
        "metadata": payload.get("metadata", {}),
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # 写消息
    (output_dir / "messages.jsonl").write_text(
        "\n".join(
            json.dumps(m, ensure_ascii=False) for m in payload.get("messages", [])
        ),
        encoding="utf-8",
    )
    # 写文件
    files_dir = output_dir / "files"
    written_files: list[str] = []
    for f in payload.get("files", []):
        files_dir.mkdir(exist_ok=True)
        name = f.get("name") or "unnamed"
        # 防 path traversal
        safe = Path(name).name
        target = files_dir / safe
        try:
            raw = base64.b64decode(f["content_b64"])
        except Exception as e:
            raise FetchError(f"文件 {name} base64 解码失败: {e}") from e
        target.write_bytes(raw)
        written_files.append(str(target))
    return {
        "metadata": str(output_dir / "metadata.json"),
        "messages": str(output_dir / "messages.jsonl"),
        "files": written_files,
        "output_dir": str(output_dir),
    }


def fetch_and_decrypt(
    handoff_key: str,
    server_url: str,
    output_dir: Optional[str] = None,
) -> dict:
    """一站式:解析 key + 拉取 + 解密 + 落盘。

    返回:
    ```
    {
      "output_dir": "...",
      "metadata": "...",
      "messages": "...",
      "files": ["..."],
      "n_messages": 10,
      "n_files": 3,
      "source": {...},
    }
    ```
    """
    bundle_id, enc_key = parse_handoff_key(handoff_key)
    if not server_url:
        raise FetchError("server_url 必填")

    blob = fetch_bundle(server_url, bundle_id)
    payload = decrypt_bundle(
        bundle_id=bundle_id,
        ciphertext_b64=blob["ciphertext_b64"],
        nonce_b64=blob["nonce_b64"],
        enc_key=enc_key,
    )
    if output_dir is None:
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        output_dir = f"./handoff/{bundle_id}-{ts}"
    summary = write_to_disk(payload, Path(output_dir))
    summary.update(
        {
            "n_messages": len(payload.get("messages", [])),
            "n_files": len(payload.get("files", [])),
            "source": payload.get("source", {}),
            "created_at": payload.get("created_at"),
            "metadata_payload": payload.get("metadata", {}),
        }
    )
    return summary
