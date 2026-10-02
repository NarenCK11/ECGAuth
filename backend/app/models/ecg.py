import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, JSONType, UTCDateTime
from app.models.user import utcnow


class ECGEnrollment(Base):
    """The enrolled ECG recording is the patient's credential.

    Only SHA-256 digests of the uploaded files are kept - the raw files are discarded.
    """

    __tablename__ = "ecg_enrollments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    hea_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dat_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)  # .hea name
    dat_filename: Mapped[str | None] = mapped_column(String(255))
    sampling_rate: Mapped[float | None] = mapped_column(Float)
    sample_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, nullable=False
    )

    user = relationship("User", back_populates="enrollment")

    # The same recording cannot serve as two different patients' credential.
    __table_args__ = (UniqueConstraint("hea_hash", "dat_hash", name="uq_enrollment_file_hashes"),)


class AnalysisProfile(Base):
    """Deterministic analysis visualisation, generated once at enrollment and reused on every login."""

    __tablename__ = "analysis_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    enrollment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ecg_enrollments.id", ondelete="CASCADE")
    )
    pipeline_version: Mapped[str] = mapped_column(String(32), nullable=False)
    signal_data: Mapped[dict] = mapped_column(JSONType, nullable=False)
    processed_signal_data: Mapped[dict] = mapped_column(JSONType, nullable=False)
    feature_data: Mapped[dict] = mapped_column(JSONType, nullable=False)
    stage_data: Mapped[dict] = mapped_column(JSONType, nullable=False)
    display_metrics: Mapped[dict] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id", "pipeline_version", name="uq_profile_user_version"),)
