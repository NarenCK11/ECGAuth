"""Demonstration medical records. All doctors, diagnoses and reports are fictional."""
import hashlib
import uuid
from datetime import date, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MedicalRecord, User

TEMPLATES = [
    dict(department="Cardiology", record_type="ECG Examination", doctor="Dr. Meera Iyer",
         diagnosis="Normal sinus rhythm",
         notes="12-lead resting ECG reviewed. Regular rhythm, normal axis, no acute ST-T changes.",
         report_title="Resting ECG report", report_summary="Rate 68 bpm. PR 160 ms, QRS 92 ms, QTc 410 ms. Within normal limits."),
    dict(department="General Medicine", record_type="Routine Consultation", doctor="Dr. Arjun Menon",
         diagnosis="Routine check-up",
         notes="Patient reports no complaints. Vitals stable. Advised regular exercise and balanced diet.",
         report_title=None, report_summary=None),
    dict(department="Cardiology", record_type="Follow-up", doctor="Dr. Meera Iyer",
         diagnosis="Mild palpitations, no arrhythmia detected",
         notes="Symptoms resolved with reduced caffeine intake. Continue monitoring; review in six months.",
         report_title="24-hour Holter summary", report_summary="No sustained arrhythmia. Occasional isolated ectopic beats (<1%)."),
    dict(department="Laboratory", record_type="Blood Panel", doctor="Dr. Sana Qureshi",
         diagnosis="Lipid profile borderline",
         notes="LDL slightly above target. Dietary advice given; repeat panel in three months.",
         report_title="Lipid & metabolic panel", report_summary="Total cholesterol 201 mg/dL, LDL 128 mg/dL, HDL 52 mg/dL, fasting glucose 92 mg/dL."),
    dict(department="Radiology", record_type="Chest X-ray", doctor="Dr. Rohan Das",
         diagnosis="No acute cardiopulmonary abnormality",
         notes="PA view. Clear lung fields, normal cardiac silhouette.",
         report_title="Chest X-ray report", report_summary="Heart size normal. No consolidation, effusion or pneumothorax."),
    dict(department="General Medicine", record_type="Vaccination", doctor="Nurse L. Thomas",
         diagnosis=None, notes="Seasonal influenza vaccine administered, left deltoid. No immediate reaction.",
         report_title=None, report_summary=None),
    dict(department="Cardiology", record_type="Stress Test", doctor="Dr. Meera Iyer",
         diagnosis="Good exercise tolerance",
         notes="Treadmill protocol completed to target heart rate. No ischemic changes or symptoms.",
         report_title="Treadmill stress test", report_summary="9 METs achieved. Peak HR 162 bpm. Blood pressure response normal."),
]
OFFSETS_DAYS = [0, 17, 53, 84, 130, 177, 240]


def seed_demo_records(db: Session, user: User, today: date | None = None) -> list[MedicalRecord]:
    """Create a deterministic set of demo records for *user* (selection depends only on the user's UUID)."""
    digest = hashlib.sha256(user.id.bytes).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    count = int(rng.integers(5, len(TEMPLATES) + 1))
    chosen = list(rng.permutation(len(TEMPLATES))[:count])
    # Always include a cardiology ECG examination first so the demo story holds together.
    chosen = [0] + [i for i in chosen if i != 0][: count - 1]
    today = today or date.today()
    rows = []
    for slot, ti in enumerate(chosen):
        t = TEMPLATES[ti]
        rows.append(MedicalRecord(user_id=user.id, record_date=today - timedelta(days=OFFSETS_DAYS[slot]), **t))
    db.add_all(rows)
    return rows


def list_records(db: Session, user_id: uuid.UUID) -> list[MedicalRecord]:
    return list(db.scalars(
        select(MedicalRecord).where(MedicalRecord.user_id == user_id).order_by(MedicalRecord.record_date.desc(), MedicalRecord.created_at.desc())
    ))


def get_record(db: Session, user_id: uuid.UUID, record_id: uuid.UUID) -> MedicalRecord | None:
    """Only ever returns a record that belongs to *user_id*."""
    return db.scalar(select(MedicalRecord).where(MedicalRecord.id == record_id, MedicalRecord.user_id == user_id))
