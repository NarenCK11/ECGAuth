import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import CI_COLLATION, Base, UTCDateTime


class Role(str, enum.Enum):
    patient = "patient"
    admin = "admin"


class UserStatus(str, enum.Enum):
    pending = "pending"    # registered, ECG not yet enrolled
    active = "active"
    inactive = "inactive"  # deactivated by an administrator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """UUID is the canonical identity; `patient_number` is only a display label (PT-1042)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Display number for patients (PT-1001, ...), assigned by the registration service; admins have none.
    patient_number: Mapped[int | None] = mapped_column(Integer, unique=True)
    username: Mapped[str] = mapped_column(String(32, collation=CI_COLLATION), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254, collation=CI_COLLATION), unique=True, nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=Role.patient.value)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=UserStatus.pending.value)
    # Only administrators have a password; patients authenticate with their enrolled ECG.
    password_hash: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)

    enrollment = relationship("ECGEnrollment", back_populates="user", uselist=False, cascade="all, delete-orphan")

    @property
    def patient_id(self) -> str | None:
        """Display label for patients only; administrators have none."""
        if self.patient_number is None:
            return None
        return f"PT-{self.patient_number}"
