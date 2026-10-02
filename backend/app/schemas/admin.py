import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.user import UserOut


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class AdminLoginResponse(BaseModel):
    username: str
    role: str


class StatusUpdate(BaseModel):
    status: Literal["active", "inactive"]


class AuthEventOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    user_id: uuid.UUID | None
    patient_id: str | None
    username: str | None
    full_name: str | None
    result: str
    failure_reason: str | None
    method: str
    pipeline_version: str | None
    processing_time_ms: int | None


class AuthEventPage(BaseModel):
    total: int
    items: list[AuthEventOut]


class AdminUserRow(UserOut):
    enrolled: bool
    auth_total: int
    auth_failed: int
    last_auth_at: datetime | None


class AdminUserPage(BaseModel):
    total: int
    items: list[AdminUserRow]


class AdminUserDetail(BaseModel):
    user: AdminUserRow
    enrollment_reference: str | None
    recent_events: list[AuthEventOut]


class AuditLogOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    actor_id: uuid.UUID | None
    actor_role: str
    actor_name: str | None
    action: str
    metadata: dict[str, Any] | None


class AuditLogPage(BaseModel):
    total: int
    items: list[AuditLogOut]
