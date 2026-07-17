"""上传/拉取/删除路由。"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from ..config import Settings, get_settings
from ..models import FetchResponse, UploadRequest, UploadResponse
from ..storage import StorageBackend

router = APIRouter(prefix="/api/v1/bundles", tags=["bundles"])


def get_storage(request: Request) -> StorageBackend:
    storage: Optional[StorageBackend] = getattr(request.app.state, "storage", None)
    if storage is None:
        raise HTTPException(status_code=500, detail="storage not initialized")
    return storage


def _check_admin(authorization: Optional[str], settings: Settings) -> None:
    """校验管理操作需要带 admin token。"""
    if not authorization:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing Authorization header")
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if token != settings.admin_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid admin token")


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
def upload(
    body: UploadRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    storage = get_storage(request)

    # 大小校验
    total = len(body.ciphertext_b64.encode("utf-8")) + len(body.nonce_b64.encode("utf-8"))
    if total > settings.max_bundle_size:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"bundle too large: {total} > {settings.max_bundle_size}",
        )

    # 校验 base64 格式
    try:
        base64.b64decode(body.ciphertext_b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"ciphertext_b64 invalid: {e}")
    try:
        nonce = base64.b64decode(body.nonce_b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"nonce_b64 invalid: {e}")
    if len(nonce) != 12:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "nonce must be 12 bytes")

    # 校验 id 长度
    if len(body.id) != settings.bundle_id_length:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"id 长度必须是 {settings.bundle_id_length} 字符 hex",
        )

    # 过期时间
    expires_in = body.expires_in or settings.default_expires_in
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    meta = storage.put(
        body.id, body.ciphertext_b64, body.nonce_b64, hint=body.hint, expires_at=expires_at
    )
    return UploadResponse(id=meta.id, expires_at=meta.expires_at, size=meta.size)


@router.get("/{bundle_id}", response_model=FetchResponse)
def fetch(
    bundle_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> FetchResponse:
    storage = get_storage(request)
    bundle = storage.get(bundle_id)
    if bundle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "bundle not found")
    now = datetime.now(timezone.utc)
    if bundle.expires_at and bundle.expires_at < now:
        raise HTTPException(status.HTTP_410_GONE, "bundle expired")
    if bundle.consumed and settings.one_time_consume:
        raise HTTPException(status.HTTP_410_GONE, "bundle already consumed")

    # 一次性消费:标记 consumed(但不立即删除,留给后台清理)
    if settings.one_time_consume:
        storage.mark_consumed(bundle_id)

    return FetchResponse(
        id=bundle.id,
        ciphertext_b64=bundle.ciphertext_b64,
        nonce_b64=bundle.nonce_b64,
        hint=bundle.hint,
        expires_at=bundle.expires_at,
        consumed=bundle.consumed,
    )


@router.delete("/{bundle_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete(
    bundle_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
    authorization: Optional[str] = Header(default=None),
) -> Response:
    _check_admin(authorization, settings)
    storage = get_storage(request)
    storage.delete(bundle_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
