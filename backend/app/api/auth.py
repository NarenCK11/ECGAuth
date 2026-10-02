import time

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    clear_session_cookie, client_ip, current_patient, enrolling_user, get_ml, set_session_cookie, user_from_cookie,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import ENROLL_COOKIE, PATIENT_COOKIE, TYPE_ENROLL, TYPE_PATIENT
from app.models import Role, User
from app.schemas.auth import EnrollResponse, LoginResponse, MeResponse, RegisterRequest, RegisterResponse
from app.schemas.user import UserOut
from app.services import authentication_service as svc
from app.services.ecg_service import ECGValidationError, read_upload
from app.services.ml_service import ECGModelService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(body: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Step 1: create the account. The caller then has a short-lived enrollment session."""
    user = svc.register_user(db, body, client_ip(request))
    set_session_cookie(response, ENROLL_COOKIE, user.id, TYPE_ENROLL)
    return RegisterResponse(user=UserOut.model_validate(user))


@router.post("/enroll", response_model=EnrollResponse)
async def enroll(
    request: Request,
    response: Response,
    hea_file: UploadFile = File(...),
    dat_file: UploadFile = File(...),
    user: User = Depends(enrolling_user),
    db: Session = Depends(get_db),
    ml: ECGModelService = Depends(get_ml),
):
    """Step 2: upload the .hea + .dat recording that becomes the account's credential."""
    try:
        upload = await read_upload(hea_file, dat_file, get_settings().max_upload_bytes)
    except ECGValidationError as e:
        raise svc.ServiceError(400, str(e))
    enrollment = svc.enroll_user(db, user, upload, ml, client_ip(request))
    db.refresh(user)
    clear_session_cookie(response, ENROLL_COOKIE)
    return EnrollResponse(
        user=UserOut.model_validate(user), enrollment_reference=svc.enrollment_reference(enrollment),
        message="ECG enrolled. You can now sign in with your recording.",
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    username: str = Form(..., min_length=1, max_length=64),
    hea_file: UploadFile = File(...),
    dat_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    ml: ECGModelService = Depends(get_ml),
):
    """Authenticate with username (or patient ID) + the enrolled ECG files.

    The decision is made here, server-side. A session cookie is issued only on success; a
    failure still returns the analysis of the *uploaded* recording, never the enrolled one.
    """
    started = time.perf_counter()
    try:
        upload = await read_upload(hea_file, dat_file, get_settings().max_upload_bytes)
    except ECGValidationError as e:
        raise svc.ServiceError(400, str(e))
    outcome = svc.authenticate_patient(db, username, upload, client_ip(request), started, ml)
    body = LoginResponse(
        authenticated=outcome.authenticated, message=outcome.message,
        user=UserOut.model_validate(outcome.user) if outcome.user else None,
        attempt_id=str(outcome.attempt.id), analysis=outcome.analysis,
    )
    if not outcome.authenticated:
        return JSONResponse(status_code=401, content=body.model_dump(mode="json"))
    resp = JSONResponse(content=body.model_dump(mode="json"))
    set_session_cookie(resp, PATIENT_COOKIE, outcome.user.id, TYPE_PATIENT)
    return resp


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    user = user_from_cookie(request, db, PATIENT_COOKIE, TYPE_PATIENT)
    if user:
        svc.audit(db, user.id, Role.patient.value, "logout", ip=client_ip(request))
        db.commit()
    clear_session_cookie(response, PATIENT_COOKIE)
    response.status_code = 204
    return response


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(current_patient)):
    return MeResponse(authenticated=True, user=UserOut.model_validate(user))
