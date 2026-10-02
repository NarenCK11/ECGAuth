import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UTCDateTime
from app.models.user import utcnow


class AuthResult(str, enum.Enum):
    success = "success"
    failure = "failure"


class AuthMethod(str, enum.Enum):
    ecg_hash = "ecg_hash"    # application enrollment: exact-file verification
    ecg_model = "ecg_model"  # legacy trained identities via the ML model


class AuthenticationAttempt(Base):
    __tablename__ = "authentication_attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # NULL when the username did not match any account (the attempted name is kept for the audit trail).
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    username_attempted: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(64))
    authentication_method: Mapped[str] = mapped_column(String(16), nullable=False, default=AuthMethod.ecg_hash.value)
    analysis_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("analysis_profiles.id", ondelete="SET NULL")
    )
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_auth_attempts_user_created", "user_id", "created_at"),
        Index("ix_auth_attempts_created", "created_at"),
    )
