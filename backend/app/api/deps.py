"""Request dependencies: server-side session and role checks.

Identity always comes from the signed session cookie and is re-checked against the database on
every request (so deactivating an account takes effect immediately). Nothing in a request body
or query string can establish who the caller is.
"""
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    ADMIN_COOKIE, ENROLL_COOKIE, PATIENT_COOKIE, TYPE_ADMIN, TYPE_ENROLL, TYPE_PATIENT, create_token, decode_token,
)
from app.models import Role, User, UserStatus
from app.services.ml_service import ECGModelService


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_ml(request: Request) -> ECGModelService:
    return request.app.state.ml


def set_session_cookie(response: Response, name: str, user_id, token_type: str) -> None:
    s = get_settings()
    token, max_age = create_token(user_id, token_type)
    response.set_cookie(
        name, token, max_age=max_age, httponly=True, secure=s.cookie_secure, samesite=s.cookie_samesite,
        path="/api/admin" if name == ADMIN_COOKIE else "/api",
    )


def clear_session_cookie(response: Response, name: str) -> None:
    response.delete_cookie(name, path="/api/admin" if name == ADMIN_COOKIE else "/api")


def user_from_cookie(request: Request, db: Session, cookie: str, token_type: str) -> User | None:
    uid = decode_token(request.cookies.get(cookie), token_type)
    return db.get(User, uid) if uid else None


def current_patient(request: Request, db: Session = Depends(get_db)) -> User:
    user = user_from_cookie(request, db, PATIENT_COOKIE, TYPE_PATIENT)
    if not user or user.role != Role.patient.value or user.status != UserStatus.active.value:
        raise HTTPException(401, "Authentication required.")
    return user


def current_admin(request: Request, db: Session = Depends(get_db)) -> User:
    user = user_from_cookie(request, db, ADMIN_COOKIE, TYPE_ADMIN)
    if not user or user.role != Role.admin.value or user.status != UserStatus.active.value:
        raise HTTPException(401, "Administrator authentication required.")
    return user


def enrolling_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = user_from_cookie(request, db, ENROLL_COOKIE, TYPE_ENROLL)
    if not user or user.role != Role.patient.value or user.status != UserStatus.pending.value:
        raise HTTPException(401, "Registration session expired. Please register again.")
    return user
