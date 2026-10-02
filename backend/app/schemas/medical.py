import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict

DEMO_DISCLAIMER = (
    "Demonstration environment: all records, doctors and reports shown here are fictional "
    "sample data. This is not a real medical-record system."
)


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    record_date: date
    department: str
    doctor: str
    record_type: str
    diagnosis: str | None
    notes: str | None
    report_title: str | None
    report_summary: str | None


class RecordList(BaseModel):
    disclaimer: str = DEMO_DISCLAIMER
    items: list[RecordOut]
