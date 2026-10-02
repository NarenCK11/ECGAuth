import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Index, String, Text
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UTCDateTime
from app.models.user import utcnow


class MedicalRecord(Base):
    """Seeded demonstration data - this is not a real medical-record system."""

    __tablename__ = "medical_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    department: Mapped[str] = mapped_column(String(80), nullable=False)
    doctor: Mapped[str] = mapped_column(String(120), nullable=False)
    record_type: Mapped[str] = mapped_column(String(80), nullable=False)
    diagnosis: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    report_title: Mapped[str | None] = mapped_column(String(160))    # attached (demo) report
    report_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, nullable=False
    )

    __table_args__ = (Index("ix_medical_records_user_date", "user_id", "record_date"),)
