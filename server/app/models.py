"""Pydantic 模型:请求/响应。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class UploadRequest(BaseModel):
    """客户端上传密文。"""

    id: str = Field(..., description="Bundle ID, hex 字符")
    ciphertext_b64: str = Field(..., description="AES-GCM 密文 + tag, base64")
    nonce_b64: str = Field(..., description="12 字节 nonce, base64")
    expires_in: Optional[int] = Field(None, ge=60, le=30 * 24 * 3600, description="秒")
    hint: Optional[str] = Field(None, max_length=200, description="用户备注")

    @field_validator("id")
    @classmethod
    def _id_hex(cls, v: str) -> str:
        v = v.strip().lower()
        if not v or len(v) % 2 != 0:
            raise ValueError("id 必须是偶数长度 hex 字符串")
        try:
            bytes.fromhex(v)
        except ValueError as e:
            raise ValueError(f"id 不是合法 hex: {e}") from e
        return v


class UploadResponse(BaseModel):
    id: str
    expires_at: datetime
    size: int


class FetchResponse(BaseModel):
    id: str
    ciphertext_b64: str
    nonce_b64: str
    hint: Optional[str] = None
    expires_at: datetime
    consumed: bool = False


class HealthResponse(BaseModel):
    status: str
    storage: str
    version: str
