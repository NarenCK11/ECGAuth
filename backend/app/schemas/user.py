import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: str | None
    username: str
    full_name: str
    email: str
    date_of_birth: date | None
    role: str
    status: str
    created_at: datetime


class EnrollmentOut(BaseModel):
    reference: str            # ENR-xxxxxxxx (short enrollment id)
    original_filename: str
    sampling_rate: float | None
    sample_count: int | None
    enrolled_at: datetime


class ProfileOut(BaseModel):
    user: UserOut
    enrollment: EnrollmentOut | None
    authentication_count: int
    last_authenticated_at: datetime | None
