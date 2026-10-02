from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.admin import _event_rows, _user_rows
from app.api.deps import current_admin
from app.core.database import get_db
from app.models import AuditLog, AuthenticationAttempt, AuthResult, Role, User, UserStatus
from app.models.user import utcnow
from app.services.analysis_service import PIPELINE_VERSION

router = APIRouter(prefix="/api/admin", tags=["admin"])

S, F = AuthResult.success.value, AuthResult.failure.value


def _day_start(d: date) -> datetime:
    return datetime.combine(d, dtime.min, tzinfo=timezone.utc)


def _daily(db: Session, days: int) -> list[dict[str, Any]]:
    today = utcnow().date()
    first = today - timedelta(days=days - 1)
    day = func.date(AuthenticationAttempt.created_at)
    rows = db.execute(
        select(
            day.label("d"),
            func.sum(case((AuthenticationAttempt.result == S, 1), else_=0)),
            func.sum(case((AuthenticationAttempt.result == F, 1), else_=0)),
            func.avg(AuthenticationAttempt.processing_time_ms),
        ).where(AuthenticationAttempt.created_at >= _day_start(first)).group_by(day)
    ).all()
    by_day = {(d if isinstance(d, date) else date.fromisoformat(str(d))): (s, f, a) for d, s, f, a in rows}
    out = []
    for i in range(days):
        d = first + timedelta(days=i)
        s, f, a = by_day.get(d, (0, 0, None))
        out.append({"date": d.isoformat(), "success": int(s or 0), "failure": int(f or 0),
                    "avg_ms": round(float(a), 1) if a is not None else None})
    return out


@router.get("/dashboard")
def dashboard(request: Request, _: User = Depends(current_admin), db: Session = Depends(get_db)):
    now = utcnow()
    patients = User.role == Role.patient.value
    registered = db.scalar(select(func.count()).where(patients, User.status != UserStatus.pending.value)) or 0
    pending = db.scalar(select(func.count()).where(patients, User.status == UserStatus.pending.value)) or 0
    total, ok, bad = db.execute(select(
        func.count(), func.sum(case((AuthenticationAttempt.result == S, 1), else_=0)),
        func.sum(case((AuthenticationAttempt.result == F, 1), else_=0)),
    )).one()
    active_7d = db.scalar(select(func.count(func.distinct(AuthenticationAttempt.user_id))).where(
        AuthenticationAttempt.result == S, AuthenticationAttempt.created_at >= now - timedelta(days=7))) or 0
    failed_24h = db.scalar(select(func.count()).where(
        AuthenticationAttempt.result == F, AuthenticationAttempt.created_at >= now - timedelta(hours=24))) or 0

    _, recent_events = _event_rows(db, [], 10, 0)
    _, recent_users = _user_rows(db, [], 1000, 0)
    recent_users = sorted(recent_users, key=lambda u: u.created_at, reverse=True)[:5]
    logs = db.execute(
        select(AuditLog, User.username).outerjoin(User, User.id == AuditLog.actor_id)
        .order_by(AuditLog.created_at.desc()).limit(8)
    ).all()

    return {
        "totals": {"registered_users": int(registered), "pending_users": int(pending), "authentication_events": int(total or 0),
                   "successful": int(ok or 0), "failed": int(bad or 0), "active_users_7d": int(active_7d),
                   "failed_24h": int(failed_24h)},
        "trend": _daily(db, 14),
        "recent_events": [e.model_dump(mode="json") for e in recent_events],
        "recent_registrations": [u.model_dump(mode="json") for u in recent_users],
        "system": {
            "ml_available": request.app.state.ml.available, "pipeline_version": PIPELINE_VERSION,
            "recent_activity": [
                {"id": str(a.id), "created_at": a.created_at.isoformat(), "action": a.action, "actor_role": a.actor_role,
                 "actor_name": name} for a, name in logs
            ],
        },
    }


@router.get("/analytics")
def analytics(_: User = Depends(current_admin), db: Session = Depends(get_db)):
    since = utcnow() - timedelta(days=30)
    recent = AuthenticationAttempt.created_at >= since

    by_method = db.execute(
        select(AuthenticationAttempt.authentication_method, func.count()).where(recent)
        .group_by(AuthenticationAttempt.authentication_method)).all()
    reasons = db.execute(
        select(AuthenticationAttempt.failure_reason, func.count())
        .where(recent, AuthenticationAttempt.result == F).group_by(AuthenticationAttempt.failure_reason)
        .order_by(func.count().desc())).all()
    hours = dict(db.execute(select(func.hour(AuthenticationAttempt.created_at), func.count()).where(recent)
                            .group_by(func.hour(AuthenticationAttempt.created_at))).all())
    top_failed = db.execute(
        select(AuthenticationAttempt.username_attempted, func.count().label("n"))
        .where(recent, AuthenticationAttempt.result == F).group_by(AuthenticationAttempt.username_attempted)
        .order_by(func.count().desc()).limit(5)).all()
    statuses = db.execute(select(User.status, func.count()).where(User.role == Role.patient.value).group_by(User.status)).all()
    durations = sorted(x for (x,) in db.execute(
        select(AuthenticationAttempt.processing_time_ms).where(recent, AuthenticationAttempt.processing_time_ms.is_not(None))).all())

    def pct(p: float) -> int | None:
        return durations[min(len(durations) - 1, int(p * len(durations)))] if durations else None

    return {
        "daily": _daily(db, 30),
        "by_method": [{"method": m, "count": int(c)} for m, c in by_method],
        "failure_reasons": [{"reason": r or "unspecified", "count": int(c)} for r, c in reasons],
        "hourly_utc": [{"hour": h, "count": int(hours.get(h, 0))} for h in range(24)],
        "top_failed_usernames": [{"username": u, "count": int(c)} for u, c in top_failed],
        "user_status": [{"status": s, "count": int(c)} for s, c in statuses],
        "processing_ms": {"avg": round(sum(durations) / len(durations), 1) if durations else None,
                          "p50": pct(0.5), "p95": pct(0.95), "samples": len(durations)},
    }
