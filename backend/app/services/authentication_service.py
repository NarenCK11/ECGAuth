"""Registration, enrollment, ECG login and admin login.

The authentication decision is made here, on the server, and nowhere else. For application
users the enrolled ECG files are the credential: login succeeds only if the SHA-256 digests of
*both* uploaded files equal the enrolled digests. The ML model is not involved.

The pre-trained model identities (names in user_mapping.json) have no application account; they
are analysed by the original model (`identify_with_model`) and never receive a session.
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import DUMMY_HASH, digests_equal, hash_password, verify_password
from app.models import (
    AnalysisProfile, AuditLog, AuthenticationAttempt, AuthMethod, AuthResult, ECGEnrollment, Role, User, UserStatus,
)
from app.ml.inference import Prediction
from app.models.user import utcnow
from app.schemas.auth import RegisterRequest
from app.services import analysis_service as an
from app.services import simulated_ml as sim
from app.services.ecg_service import ECGValidationError, UploadedECG, parse_ecg
from app.services.medical_record_service import seed_demo_records
from app.services.ml_service import ECGModelService

FIRST_PATIENT_NUMBER = 1001  # first patient is PT-1001
GENERIC_FAILURE = "Authentication failed. Check your username and ECG recording."


class ServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


def audit(db: Session, actor_id: uuid.UUID | None, actor_role: str, action: str, **meta: Any) -> None:
    db.add(AuditLog(actor_id=actor_id, actor_role=actor_role, action=action, meta=meta or None))


def enrollment_reference(e: ECGEnrollment | None) -> str | None:
    return f"ENR-{e.id.hex[:8].upper()}" if e else None


# --- registration / enrollment -----------------------------------------------------------------
def register_user(db: Session, data: RegisterRequest, ip: str | None, ml: ECGModelService | None = None) -> User:
    if model_identity_exists(ml, data.username):  # keep the trained identities' names unambiguous
        raise ServiceError(409, "That username is reserved.")
    for _ in range(5):
        # Next display number. Two simultaneous registrations can pick the same one; the unique
        # key rejects the loser, which simply retries with a fresh number.
        next_number = (db.scalar(select(func.max(User.patient_number))) or FIRST_PATIENT_NUMBER - 1) + 1
        user = User(
            patient_number=next_number, username=data.username, full_name=data.full_name, email=data.email,
            date_of_birth=data.date_of_birth, role=Role.patient.value, status=UserStatus.pending.value,
        )
        db.add(user)
        try:
            db.flush()
            break
        except IntegrityError as e:
            db.rollback()
            if "patient_number" in str(e.orig):
                continue
            raise ServiceError(409, "That username or email is already registered.")
    else:
        raise ServiceError(503, "Registration is busy. Please try again.")
    audit(db, user.id, Role.patient.value, "register", ip=ip)
    db.commit()
    return user


def enroll_user(db: Session, user: User, upload: UploadedECG, ip: str | None) -> ECGEnrollment:
    """Store the enrollment (SHA-256 digests) and the user's seeded analysis profile. The ML model is never used."""
    if user.status != UserStatus.pending.value or user.enrollment is not None:
        raise ServiceError(409, "This account already has an enrolled ECG.")
    try:
        parsed = parse_ecg(upload)
    except ECGValidationError as e:
        raise ServiceError(400, str(e))

    enrollment = ECGEnrollment(
        user_id=user.id, hea_hash=upload.hea_hash, dat_hash=upload.dat_hash,
        original_filename=upload.hea_filename, dat_filename=upload.dat_filename,
        sampling_rate=parsed.fs, sample_count=int(parsed.signal.size),
    )
    db.add(enrollment)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ServiceError(409, "This ECG recording is already enrolled. Please use your own recording.")

    data = _profile_for_user(user, parsed, upload)
    db.add(AnalysisProfile(user_id=user.id, enrollment_id=enrollment.id, pipeline_version=an.PIPELINE_VERSION, **data))
    user.status = UserStatus.active.value
    seed_demo_records(db, user)
    audit(db, user.id, Role.patient.value, "enroll", enrollment=enrollment_reference(enrollment), ip=ip)
    db.commit()
    return enrollment


def _profile_for_user(user: User, parsed, upload: UploadedECG) -> dict[str, Any]:
    """Analysis profile for a registered account: seeded by the user's UUID, no ML (see simulated_ml)."""
    seed = str(user.id)
    return an.build_profile_data(
        parsed, upload.hea_hash, upload.dat_hash, embedding=sim.simulated_embedding(seed),
        identity=sim.simulate_identity(seed, user.full_name, True),
    )


# --- patient login -----------------------------------------------------------------------------
@dataclass
class LoginOutcome:
    authenticated: bool
    user: User | None
    attempt: AuthenticationAttempt
    analysis: dict[str, Any]
    message: str


def find_user(db: Session, identifier: str) -> User | None:
    """Accepts a username or a patient ID such as PT-1042."""
    ident = identifier.strip().lower()
    m = re.fullmatch(r"pt-(\d{1,9})", ident)
    if m:
        return db.scalar(select(User).where(User.patient_number == int(m.group(1)), User.role == Role.patient.value))
    return db.scalar(select(User).where(User.username == ident))


def _recent_failures(db: Session, ident: str, ip: str | None) -> int:
    s = get_settings()
    since = utcnow() - timedelta(minutes=s.login_lockout_minutes)
    q = select(func.count()).select_from(AuthenticationAttempt).where(
        AuthenticationAttempt.username_attempted == ident,
        AuthenticationAttempt.result == AuthResult.failure.value,
        AuthenticationAttempt.created_at >= since,
    )
    if ip:
        q = q.where(AuthenticationAttempt.ip_address == ip)
    return int(db.scalar(q) or 0)


def authenticate_patient(
    db: Session, identifier: str, upload: UploadedECG, ip: str | None, started: float | None = None,
) -> LoginOutcome:
    started = started if started is not None else time.perf_counter()
    s = get_settings()
    ident = identifier.strip().lower()[:64]
    if _recent_failures(db, ident, ip) >= s.login_max_failures:
        raise ServiceError(429, "Too many failed attempts. Please wait a few minutes and try again.")

    user = find_user(db, ident)
    if user is not None and user.role != Role.patient.value:
        user = None  # administrators cannot use the patient login; treated like an unknown name
    enrollment = user.enrollment if user else None

    reason: str | None
    if user is None:
        reason = "unknown_user"
    elif user.status == UserStatus.inactive.value:
        reason = "account_inactive"
    elif user.status != UserStatus.active.value or enrollment is None:
        reason = "not_enrolled"
    else:
        reason = None

    # Always compare both digests (constant time) so timing does not depend on which file differs.
    matched = False
    if reason is None:
        hea_ok = digests_equal(enrollment.hea_hash, upload.hea_hash)
        dat_ok = digests_equal(enrollment.dat_hash, upload.dat_hash)
        matched = hea_ok and dat_ok
        if not matched:
            reason = "ecg_mismatch"

    profile_row: AnalysisProfile | None = None
    if matched:
        profile_row = db.scalar(select(AnalysisProfile).where(
            AnalysisProfile.user_id == user.id, AnalysisProfile.pipeline_version == an.PIPELINE_VERSION))
        if profile_row is None:  # e.g. pipeline version bumped; the file is proven identical to the enrolled one
            data = _profile_for_user(user, parse_ecg(upload), upload)
            profile_row = AnalysisProfile(user_id=user.id, enrollment_id=enrollment.id,
                                          pipeline_version=an.PIPELINE_VERSION, **data)
            db.add(profile_row)
            db.flush()
        profile = an.profile_to_dict(profile_row)
        info = profile_row.display_metrics.get("identity") or sim.simulate_identity(str(user.id), user.full_name, True)
    else:
        # Never return the enrolled user's data to someone who failed: visualise what was uploaded.
        try:
            uploaded_parsed = parse_ecg(upload)
        except ECGValidationError as e:
            _record_attempt(db, user, ident, False, "invalid_files", None, started, ip)
            db.commit()
            raise ServiceError(400, str(e))
        # Seeded from the uploaded files + claimed name: same upload, same output; no ML involved.
        seed = f"{upload.hea_hash}{upload.dat_hash}{ident}"
        info = sim.simulate_identity(seed, None, False, exclude=ident)
        profile = an.build_profile_data(uploaded_parsed, upload.hea_hash, upload.dat_hash,
                                        embedding=sim.simulated_embedding(seed), identity=info)

    # The displayed processing time is the seeded one on success, so history and analysis agree.
    attempt = _record_attempt(db, user, ident, matched, reason, profile_row, started, ip,
                              processing_ms=info["processing_ms"] if matched else None)
    identity = {"patient_id": user.patient_id, "name": user.full_name} if matched else None
    analysis = sim.model_style_analysis(profile, authenticated=matched, claimed=ident, info=info, identity=identity)
    message = analysis["authentication"]["message"]
    audit(db, user.id if user else None, Role.patient.value, "login_success" if matched else "login_failure",
          ip=ip, attempt=str(attempt.id), reason=reason)
    db.commit()
    return LoginOutcome(matched, user if matched else None, attempt, analysis, message)


def _record_attempt(db, user, ident, ok, reason, profile_row, started, ip, processing_ms: int | None = None) -> AuthenticationAttempt:
    attempt = AuthenticationAttempt(
        user_id=user.id if user else None, username_attempted=ident,
        result=(AuthResult.success if ok else AuthResult.failure).value, failure_reason=reason,
        authentication_method=AuthMethod.ecg_hash.value,  # the truth is kept for administrators
        analysis_profile_id=profile_row.id if profile_row else None,
        processing_time_ms=processing_ms or max(1, int((time.perf_counter() - started) * 1000)), ip_address=ip,
    )
    db.add(attempt)
    db.flush()
    return attempt


# --- admin -------------------------------------------------------------------------------------
def _admin_failures(db: Session, ip: str | None) -> int:
    s = get_settings()
    since = utcnow() - timedelta(minutes=s.login_lockout_minutes)
    rows = db.scalars(select(AuditLog.meta).where(
        AuditLog.action == "admin_login_failure", AuditLog.created_at >= since)).all()
    return sum(1 for m in rows if (m or {}).get("ip") == ip)


def authenticate_admin(db: Session, username: str, password: str, ip: str | None) -> User:
    if _admin_failures(db, ip) >= get_settings().login_max_failures:
        raise ServiceError(429, "Too many failed attempts. Please wait a few minutes and try again.")
    user = db.scalar(select(User).where(User.username == username.strip().lower(), User.role == Role.admin.value))
    ok = verify_password(password, user.password_hash if user else DUMMY_HASH)  # same cost either way
    if not user or not ok or user.status != UserStatus.active.value:
        audit(db, user.id if user else None, Role.admin.value, "admin_login_failure", ip=ip)
        db.commit()
        raise ServiceError(401, "Invalid administrator credentials.")
    audit(db, user.id, Role.admin.value, "admin_login_success", ip=ip)
    db.commit()
    return user


def ensure_admin(db: Session) -> User | None:
    """Create the initial administrator from ADMIN_USERNAME/ADMIN_PASSWORD if it does not exist.

    The password is hashed immediately; an existing admin is never modified.
    """
    s = get_settings()
    if not s.admin_username or not s.admin_password:
        return None
    username = s.admin_username.strip().lower()
    existing = db.scalar(select(User).where(User.username == username))
    if existing:
        return existing
    if len(s.admin_password) < s.min_admin_password_length:  # only when creating; default 10
        raise RuntimeError(f"ADMIN_PASSWORD must be at least {s.min_admin_password_length} characters.")
    admin = User(
        username=username, full_name="Administrator", email=f"{username}@ecgauth.local", role=Role.admin.value,
        status=UserStatus.active.value, password_hash=hash_password(s.admin_password),
    )
    db.add(admin)
    audit(db, None, Role.admin.value, "admin_bootstrap", username=username)
    db.commit()
    return admin


# --- pre-trained model identities ----------------------------------------------------------------
def model_identity_exists(ml: ECGModelService | None, identifier: str) -> bool:
    """True if *identifier* is one of the names the existing model was trained on (case-insensitive)."""
    if ml is None or not ml.available:
        return False
    key = identifier.strip().lower()
    return any(name.strip().lower() == key for name in ml.known_identities())


def identify_with_model(
    db: Session, ml: ECGModelService, identifier: str, upload: UploadedECG, ip: str | None, started: float,
) -> tuple[Prediction, dict[str, Any], AuthenticationAttempt]:
    """Run the original, unchanged model pipeline and decision rule for a trained identity.

    This never creates a session: trained identities have no application account.
    """
    ident = identifier.strip()
    key = ident.lower()[:64]
    if _recent_failures(db, key, ip) >= get_settings().login_max_failures:
        raise ServiceError(429, "Too many failed attempts. Please wait a few minutes and try again.")
    try:
        parsed = parse_ecg(upload)
    except ECGValidationError as e:
        raise ServiceError(400, str(e))

    window = parsed.signal[:1500]
    pred = ml.predict(window, ident)
    profile = an.build_profile_data(parsed, upload.hea_hash, upload.dat_hash, ml.embedding(window))
    sim = pred.similarity
    detail = f"Closest trained identity: {pred.predicted_name}" + (
        f"; score for '{ident}': {sim:.1%} (threshold {pred.threshold:.0%})" if sim is not None
        else "; claimed name not in the trained set")
    extra = [
        {"key": "similarity", "label": "Identity score (softmax of SVM margins)",
         "value": None if sim is None else round(sim * 100, 2), "unit": "%", "kind": "measured"},
        {"key": "predicted", "label": "Closest identity", "value": pred.predicted_name, "unit": "", "kind": "measured"},
    ]
    elapsed = max(1, int((time.perf_counter() - started) * 1000))
    analysis = an.build_analysis_response(
        profile, source="uploaded_file", authenticated=pred.authenticated, method=AuthMethod.ecg_model.value,
        message="Identity verified by the ECG model." if pred.authenticated else GENERIC_FAILURE,
        identity={"patient_id": None, "name": pred.predicted_name} if pred.authenticated else None,
        identity_detail=detail, extra_metrics=extra, processing_time_ms=elapsed,
    )
    attempt = AuthenticationAttempt(
        user_id=None, username_attempted=key,
        result=(AuthResult.success if pred.authenticated else AuthResult.failure).value,
        failure_reason=None if pred.authenticated else "model_mismatch",
        authentication_method=AuthMethod.ecg_model.value, processing_time_ms=elapsed, ip_address=ip,
    )
    db.add(attempt)
    db.flush()
    audit(db, None, Role.patient.value, "model_identify", ip=ip, authenticated=pred.authenticated, attempt=str(attempt.id))
    db.commit()
    return pred, analysis, attempt
