import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import current_patient
from app.core.database import get_db
from app.models import User
from app.schemas.medical import RecordList, RecordOut
from app.services import medical_record_service as svc

router = APIRouter(prefix="/api/medical-records", tags=["medical"])


@router.get("", response_model=RecordList)
def list_my_records(user: User = Depends(current_patient), db: Session = Depends(get_db)):
    return RecordList(items=svc.list_records(db, user.id))


@router.get("/{record_id}", response_model=RecordOut)
def get_my_record(record_id: uuid.UUID, user: User = Depends(current_patient), db: Session = Depends(get_db)):
    record = svc.get_record(db, user.id, record_id)
    if record is None:  # same answer whether it does not exist or belongs to someone else
        raise HTTPException(404, "Record not found.")
    return record
