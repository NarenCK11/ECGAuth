import uuid
from datetime import datetime

from sqlalchemy import Index, String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, JSONType, UTCDateTime
from app.models.user import utcnow


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Not a foreign key on purpose: the audit trail must outlive the actor.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_role: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, nullable=False
    )
    meta: Mapped[dict | None] = mapped_column("metadata", JSONType)

    __table_args__ = (Index("ix_audit_logs_created", "created_at"),)
