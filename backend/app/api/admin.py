import re
import uuid
from datetime import date, datetime, time as dtime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import clear_session_cookie, client_ip, current_admin, set_session_cookie, user_from_cookie
from app.core.database import get_db
from app.core.security import ADMIN_COOKIE, TYPE_ADMIN
from app.models import AnalysisProfile, AuditLog, AuthenticationAttempt, ECGEnrollment, Role, User, UserStatus
from app.schemas.user import UserOut
from app.schemas.admin import (
    AdminLoginRequest, AdminLoginResponse, AdminUserDetail, AdminUserPage, AdminUserRow, AuditLogOut, AuditLogPage,
    AuthEventOut, AuthEventPage, StatusUpdate,
)
from app.services import authentication_service as svc

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- session -------------------------------------------------------------------------------------
@router.post("/login", response_model=AdminLoginResponse)
def admin_login(body: AdminLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    admin = svc.authenticate_admin(db, body.username, body.password, client_ip(request))
    set_session_cookie(response, ADMIN_COOKIE, admin.id, TYPE_ADMIN)
    return AdminLoginResponse(username=admin.username, role=admin.role)


@router.post("/logout", status_code=204)
def admin_logout(request: Request, response: Response, db: Session = Depends(get_db)):
    admin = user_from_cookie(request, db, ADMIN_COOKIE, TYPE_ADMIN)
    if admin:
        svc.audit(db, admin.id, Role.admin.value, "admin_logout", ip=client_ip(request))
        db.commit()
    clear_session_cookie(response, ADMIN_COOKIE)
    response.status_code = 204
    return response


@router.get("/me", response_model=AdminLoginResponse)
def admin_me(admin: User = Depends(current_admin)):
    return AdminLoginResponse(username=admin.username, role=admin.role)


# --- helpers -------------------------------------------------------------------------------------
def _like(s: str) -> str:
    return "%" + re.sub(r"([\\%_])", r"\\\1", s.strip().lower()) + "%"


def _event_rows(db: Session, conditions: list, limit: int, offset: int) -> tuple[int, list[AuthEventOut]]:
    base = (
        select(AuthenticationAttempt, User, AnalysisProfile.pipeline_version)
        .outerjoin(User, User.id == AuthenticationAttempt.user_id)
        .outerjoin(AnalysisProfile, AnalysisProfile.id == AuthenticationAttempt.analysis_profile_id)
    )
    for c in conditions:
        base = base.where(c)
    total = db.scalar(select(func.count()).select_from(base.with_only_columns(AuthenticationAttempt.id).subquery()))
    rows = db.execute(base.order_by(AuthenticationAttempt.created_at.desc()).limit(limit).offset(offset)).all()
    items = [
        AuthEventOut(
            id=a.id, created_at=a.created_at, user_id=a.user_id, patient_id=u.patient_id if u else None,
            username=u.username if u else a.username_attempted, full_name=u.full_name if u else None,
            result=a.result, failure_reason=a.failure_reason, method=a.authentication_method,
            pipeline_version=v, processing_time_ms=a.processing_time_ms,
        ) for a, u, v in rows
    ]
    return int(total or 0), items


def _user_rows(db: Session, conditions: list, limit: int, offset: int) -> tuple[int, list[AdminUserRow]]:
    stats = (
        select(
            AuthenticationAttempt.user_id.label("uid"),
            func.count().label("total"),
            func.sum(case((AuthenticationAttempt.result == "failure", 1), else_=0)).label("failed"),
            func.max(case((AuthenticationAttempt.result == "success", AuthenticationAttempt.created_at))).label("last_ok"),
        ).where(AuthenticationAttempt.user_id.is_not(None)).group_by(AuthenticationAttempt.user_id).subquery()
    )
    q = (
        select(User, stats.c.total, stats.c.failed, stats.c.last_ok, ECGEnrollment.id)
        .outerjoin(stats, stats.c.uid == User.id)
        .outerjoin(ECGEnrollment, ECGEnrollment.user_id == User.id)
        .where(User.role == Role.patient.value, *conditions)
    )
    total = db.scalar(select(func.count()).select_from(select(User.id).where(User.role == Role.patient.value, *conditions).subquery()))
    rows = db.execute(q.order_by(User.patient_number).limit(limit).offset(offset)).all()
    items = [
        AdminUserRow(**UserOut.model_validate(u).model_dump(), enrolled=eid is not None,
                     auth_total=int(t or 0), auth_failed=int(f or 0), last_auth_at=last)
        for u, t, f, last, eid in rows
    ]
    return int(total or 0), items


# --- users ---------------------------------------------------------------------------------------
@router.get("/users", response_model=AdminUserPage)
def list_users(
    search: str | None = Query(None, max_length=100),
    status: str | None = Query(None, pattern="^(pending|active|inactive)$"),
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    _: User = Depends(current_admin), db: Session = Depends(get_db),
):
    conds = []
    if search:
        pat = _like(search)
        m = re.fullmatch(r"\s*pt-?(\d+)\s*", search.lower())
        extra = []
        if m:
            extra.append(User.patient_number == int(m.group(1)))
        try:
            extra.append(User.id == uuid.UUID(search.strip()))
        except ValueError:
            pass
        conds.append(or_(
            func.lower(User.username).like(pat, escape="\\"), func.lower(User.full_name).like(pat, escape="\\"),
            func.lower(User.email).like(pat, escape="\\"), *extra,
        ))
    if status:
        conds.append(User.status == status)
    total, items = _user_rows(db, conds, page_size, (page - 1) * page_size)
    return AdminUserPage(total=total, items=items)


def _get_patient(db: Session, user_id: uuid.UUID) -> User:
    u = db.get(User, user_id)
    if u is None or u.role != Role.patient.value:
        raise HTTPException(404, "User not found.")
    return u


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def user_detail(user_id: uuid.UUID, _: User = Depends(current_admin), db: Session = Depends(get_db)):
    u = _get_patient(db, user_id)
    _, rows = _user_rows(db, [User.id == u.id], 1, 0)
    _, events = _event_rows(db, [AuthenticationAttempt.user_id == u.id], 50, 0)
    return AdminUserDetail(user=rows[0], enrollment_reference=svc.enrollment_reference(u.enrollment), recent_events=events)


@router.patch("/users/{user_id}/status", response_model=AdminUserRow)
def set_status(user_id: uuid.UUID, body: StatusUpdate, request: Request,
               admin: User = Depends(current_admin), db: Session = Depends(get_db)):
    u = _get_patient(db, user_id)
    if u.status == UserStatus.pending.value:
        raise HTTPException(409, "This account has not completed ECG enrollment.")
    old = u.status
    if old != body.status:
        u.status = body.status
        svc.audit(db, admin.id, Role.admin.value, "user_status_changed", target=str(u.id),
                  patient_id=u.patient_id, old=old, new=body.status, ip=client_ip(request))
        db.commit()
    _, rows = _user_rows(db, [User.id == u.id], 1, 0)
    return rows[0]


# --- authentication events -----------------------------------------------------------------------
@router.get("/authentication-events", response_model=AuthEventPage)
def authentication_events(
    user: str | None = Query(None, max_length=100, description="username, name or patient ID (PT-1001)"),
    result: str | None = Query(None, pattern="^(success|failure)$"),
    date_from: date | None = None, date_to: date | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    _: User = Depends(current_admin), db: Session = Depends(get_db),
):
    conds = []
    if user:
        pat = _like(user)
        m = re.fullmatch(r"\s*pt-?(\d+)\s*", user.lower())
        conds.append(or_(
            func.lower(AuthenticationAttempt.username_attempted).like(pat, escape="\\"),
            func.lower(User.full_name).like(pat, escape="\\"),
            *( [User.patient_number == int(m.group(1))] if m else [] ),
        ))
    if result:
        conds.append(AuthenticationAttempt.result == result)
    if date_from:
        conds.append(AuthenticationAttempt.created_at >= datetime.combine(date_from, dtime.min, tzinfo=timezone.utc))
    if date_to:
        conds.append(AuthenticationAttempt.created_at < datetime.combine(date_to + timedelta(days=1), dtime.min, tzinfo=timezone.utc))
    total, items = _event_rows(db, conds, page_size, (page - 1) * page_size)
    return AuthEventPage(total=total, items=items)


# --- audit log -----------------------------------------------------------------------------------
@router.get("/audit-logs", response_model=AuditLogPage)
def audit_logs(
    action: str | None = Query(None, max_length=64),
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    _: User = Depends(current_admin), db: Session = Depends(get_db),
):
    conds = [AuditLog.action == action] if action else []
    total = db.scalar(select(func.count()).select_from(select(AuditLog.id).where(*conds).subquery()))
    rows = db.execute(
        select(AuditLog, User.username).outerjoin(User, User.id == AuditLog.actor_id).where(*conds)
        .order_by(AuditLog.created_at.desc()).limit(page_size).offset((page - 1) * page_size)
    ).all()
    items = [
        AuditLogOut(id=a.id, created_at=a.created_at, actor_id=a.actor_id, actor_role=a.actor_role, actor_name=name,
                    action=a.action, metadata=a.meta) for a, name in rows
    ]
    return AuditLogPage(total=int(total or 0), items=items)
