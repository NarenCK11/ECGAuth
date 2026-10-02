from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_patient
from app.core.database import get_db
from app.models import AuthenticationAttempt, AuthResult, User
from app.schemas.user import EnrollmentOut, ProfileOut, UserOut
from app.services.authentication_service import enrollment_reference

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=ProfileOut)
def my_profile(user: User = Depends(current_patient), db: Session = Depends(get_db)):
    e = user.enrollment
    count, last = db.execute(
        select(func.count(), func.max(AuthenticationAttempt.created_at)).where(
            AuthenticationAttempt.user_id == user.id, AuthenticationAttempt.result == AuthResult.success.value)
    ).one()
    return ProfileOut(
        user=UserOut.model_validate(user),
        enrollment=EnrollmentOut(
            reference=enrollment_reference(e), original_filename=e.original_filename,
            sampling_rate=e.sampling_rate, sample_count=e.sample_count, enrolled_at=e.created_at,
        ) if e else None,
        authentication_count=int(count or 0),
        last_authenticated_at=last,
    )
