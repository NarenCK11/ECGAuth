"""Seed demonstration data so the application is demonstrable immediately.

    python -m app.seed            # idempotent: creates whatever is missing
    python -m app.seed --reset    # DELETE ALL DATA first (development only)

Creates demo patients with UUIDs, synthetic WFDB recordings (written to ./demo_ecg so they can be
uploaded at the login screen), enrollments + deterministic analysis profiles, medical records,
a back-dated authentication history, and the administrator from ADMIN_USERNAME / ADMIN_PASSWORD.

Everything here is synthetic demonstration data.
"""
import argparse
import hashlib
import logging
import os
from datetime import timedelta
from pathlib import Path

import numpy as np
from sqlalchemy import delete, select, text

from app.core.config import REPO_ROOT, get_settings
from app.core.database import get_sessionmaker
from app.core.security import sha256_hex
from app.models import (
    AnalysisProfile, AuditLog, AuthenticationAttempt, AuthMethod, AuthResult, ECGEnrollment, MedicalRecord, Role, User,
)
from app.models.user import utcnow
from app.schemas.auth import RegisterRequest
from app.services import authentication_service as svc
from app.services.ecg_service import UploadedECG
from app.synthetic_ecg import record_bytes

log = logging.getLogger("seed")

# (username, full name, email, date of birth, ECG seed)
DEMO_PATIENTS = [
    ("naren", "Naren Kumar", "naren@example.com", "2003-03-14", 11),
    ("akhil", "Akhil Reddy", "akhil@example.com", "2002-11-02", 12),
    ("adesh", "Adesh Patil", "adesh@example.com", "2003-07-21", 13),
    ("meera", "Meera Nair", "meera@example.com", "1994-01-30", 14),
    ("rohan", "Rohan Das", "rohan@example.com", "1988-09-09", 15),
    ("sana", "Sana Qureshi", "sana@example.com", "1997-05-18", 16),
]
DEMO_DIR = Path(os.environ.get("DEMO_ECG_DIR", REPO_ROOT / "demo_ecg"))


def _reset(db) -> None:
    db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    for model in (AuditLog, AuthenticationAttempt, AnalysisProfile, MedicalRecord, ECGEnrollment, User):
        db.execute(delete(model))
    db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    db.commit()
    log.warning("All data deleted.")


def _history(db, user: User, profile: AnalysisProfile) -> int:
    """Back-dated, deterministic authentication history for the last ~3 weeks."""
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(user.id.bytes).digest()[:8], "big"))
    now, n = utcnow(), 0
    for _ in range(int(rng.integers(8, 15))):
        when = now - timedelta(days=int(rng.integers(0, 21)), hours=int(rng.integers(0, 24)), minutes=int(rng.integers(0, 60)))
        ok = bool(rng.random() > 0.18)
        # verified attempts carry the user's seeded processing time, exactly as shown in their analysis
        ms = int(profile.display_metrics["identity"]["processing_ms"]) if ok else int(rng.integers(96, 190))
        db.add(AuthenticationAttempt(
            user_id=user.id, username_attempted=user.username,
            result=(AuthResult.success if ok else AuthResult.failure).value,
            failure_reason=None if ok else "ecg_mismatch", authentication_method=AuthMethod.ecg_hash.value,
            analysis_profile_id=profile.id if ok else None, processing_time_ms=ms, ip_address="127.0.0.1", created_at=when,
        ))
        db.add(AuditLog(actor_id=user.id, actor_role=Role.patient.value,
                        action="login_success" if ok else "login_failure", created_at=when,
                        meta={"ip": "127.0.0.1", "seeded": True}))
        n += 1
    # a few attempts against names that do not exist
    for name in ("unknown.user", "jsmith"):
        when = now - timedelta(days=int(rng.integers(0, 14)), hours=int(rng.integers(0, 24)))
        db.add(AuthenticationAttempt(
            user_id=None, username_attempted=name, result=AuthResult.failure.value, failure_reason="unknown_user",
            authentication_method=AuthMethod.ecg_hash.value, processing_time_ms=int(rng.integers(96, 190)),
            ip_address="127.0.0.1", created_at=when))
    return n


def seed(reset: bool = False) -> None:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    with get_sessionmaker()() as db:
        if reset:
            _reset(db)
        for username, name, email, dob, ecg_seed in DEMO_PATIENTS:
            hea, dat = record_bytes(username, ecg_seed)
            (DEMO_DIR / f"{username}.hea").write_bytes(hea)
            (DEMO_DIR / f"{username}.dat").write_bytes(dat)
            if svc.find_user(db, username):
                log.info("exists: %s", username)
                continue
            user = svc.register_user(db, RegisterRequest(full_name=name, email=email, date_of_birth=dob, username=username), None)
            up = UploadedECG(hea, dat, f"{username}.hea", f"{username}.dat", sha256_hex(hea), sha256_hex(dat))
            svc.enroll_user(db, user, up, None)
            profile = db.scalar(select(AnalysisProfile).where(AnalysisProfile.user_id == user.id))
            _history(db, user, profile)
            db.commit()
            log.info("seeded %s (%s, UUID %s)", username, user.patient_id, user.id)
        # Administrator last, from the environment (never hard-coded).
        if svc.ensure_admin(db) is None:
            log.warning("ADMIN_USERNAME / ADMIN_PASSWORD not set: no administrator created.")

    s = get_settings()
    print(f"\nDemo patients (log in with username or Patient ID, upload the matching files from {DEMO_DIR}):")
    for username, name, *_ in DEMO_PATIENTS:
        print(f"  {username:8s} {name:14s} {username}.hea + {username}.dat")
    if s.admin_username:
        print(f"\nAdministrator: {s.admin_username} (password from ADMIN_PASSWORD) at /admin/login")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reset", action="store_true", help="delete ALL existing data first (development only)")
    seed(p.parse_args().reset)
