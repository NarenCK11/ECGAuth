import time
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, current_patient, get_ml
from app.core.config import get_settings
from app.core.database import get_db
from app.models import AnalysisProfile, AuthenticationAttempt, AuthResult, User
from app.schemas.ecg import AnalysisOut, AttemptDetail, AttemptSummary
from app.services import analysis_service as an
from app.services import authentication_service as auth_svc
from app.services import simulated_ml as sim
from app.services.ecg_service import ECGValidationError, read_upload
from app.services.ml_service import ECGModelService

router = APIRouter(prefix="/api/ecg", tags=["ecg"])


# --- legacy trained identities ------------------------------------------------------------------
@router.post("/analyze")
async def analyze_with_model(
    request: Request,
    username: str = Form(..., min_length=1, max_length=64),
    hea_file: UploadFile = File(...),
    dat_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    ml: ECGModelService = Depends(get_ml),
):
    """Identify an ECG against the *pre-trained model identities* (the original /identify behaviour).

    This path is separate from application accounts: it never creates a session and never grants
    access to the medical portal. The decision rule is the model's original one (see ml/inference.py).
    """
    started = time.perf_counter()
    started = time.perf_counter()
    if not ml.load_model():
        raise HTTPException(503, "The ECG model is not available.")
    try:
        upload = await read_upload(hea_file, dat_file, get_settings().max_upload_bytes)
    except ECGValidationError as e:
        raise auth_svc.ServiceError(400, str(e))
    pred, analysis, _ = auth_svc.identify_with_model(db, ml, username, upload, client_ip(request), started)
    return {
        "authenticated": pred.authenticated,
        "predicted_name": pred.predicted_name,
        "predicted_label": pred.predicted_label,
        "similarity": pred.similarity,
        "threshold": pred.threshold,
        "claimed_name": pred.claimed_name,
        "claimed_label": pred.claimed_label,
        "claim_idx": pred.claim_idx,
        "analysis": AnalysisOut(**analysis),
    }


# --- history for the signed-in patient ------------------------------------------------------------
def _summary(a: AuthenticationAttempt, version: str | None, ref: str | None) -> dict:
    # Patients see every attempt presented as a model-style authentication; the stored method
    # (ecg_hash vs ecg_model) remains visible to administrators.
    return dict(
        id=a.id, created_at=a.created_at, result=a.result, method="ecg_model",
        processing_time_ms=a.processing_time_ms, pipeline_version=version, enrollment_reference=ref,
        has_analysis=a.analysis_profile_id is not None,
    )


@router.get("/history", response_model=list[AttemptSummary])
def history(user: User = Depends(current_patient), db: Session = Depends(get_db)):
    ref = auth_svc.enrollment_reference(user.enrollment)
    rows = db.execute(
        select(AuthenticationAttempt, AnalysisProfile.pipeline_version)
        .outerjoin(AnalysisProfile, AnalysisProfile.id == AuthenticationAttempt.analysis_profile_id)
        .where(AuthenticationAttempt.user_id == user.id)
        .order_by(AuthenticationAttempt.created_at.desc()).limit(200)
    ).all()
    return [_summary(a, v, ref) for a, v in rows]


@router.get("/{attempt_id}", response_model=AttemptDetail)
def attempt_detail(attempt_id: uuid.UUID, user: User = Depends(current_patient), db: Session = Depends(get_db)):
    a = db.scalar(select(AuthenticationAttempt).where(
        AuthenticationAttempt.id == attempt_id, AuthenticationAttempt.user_id == user.id))
    if a is None:  # identical response for "missing" and "someone else's"
        raise HTTPException(404, "Authentication event not found.")
    ref = auth_svc.enrollment_reference(user.enrollment)
    profile = db.get(AnalysisProfile, a.analysis_profile_id) if a.analysis_profile_id else None
    summary = _summary(a, profile.pipeline_version if profile else None, ref)
    if profile is None:
        return AttemptDetail(**summary, analysis=None,
                             note="No analysis is retained for unsuccessful attempts; uploaded recordings are never stored.")
    info = profile.display_metrics.get("identity")
    if profile.pipeline_version != an.PIPELINE_VERSION or not info:
        return AttemptDetail(**summary, analysis=None,
                             note="This event was analysed with an older pipeline version and can no longer be displayed.")
    analysis = sim.model_style_analysis(
        an.profile_to_dict(profile), authenticated=a.result == AuthResult.success.value, claimed=user.username,
        info=info, identity={"patient_id": user.patient_id, "name": user.full_name},
    )
    return AttemptDetail(**summary, analysis=AnalysisOut(**analysis))
