"""Password hashing, signed session tokens, and file digests."""
import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

# Cookie names. Admin and patient sessions are completely separate.
PATIENT_COOKIE = "ecgauth_session"
ADMIN_COOKIE = "ecgauth_admin"
ENROLL_COOKIE = "ecgauth_enroll"

TYPE_PATIENT = "patient"
TYPE_ADMIN = "admin"
TYPE_ENROLL = "enroll"


# --- passwords (admin only) ------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


# Used so that unknown usernames cost the same as wrong passwords.
DUMMY_HASH = hash_password("dummy-password-for-timing")


# --- ECG file digests ------------------------------------------------------------------------
def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digests_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("ascii"), b.encode("ascii"))


# --- signed tokens ---------------------------------------------------------------------------
def create_token(subject: uuid.UUID, token_type: str, minutes: int | None = None) -> tuple[str, int]:
    """Return (jwt, max_age_seconds)."""
    s = get_settings()
    minutes = minutes if minutes is not None else (
        s.admin_session_minutes if token_type == TYPE_ADMIN else s.session_minutes
    )
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "typ": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), minutes * 60


def decode_token(token: str | None, expected_type: str) -> uuid.UUID | None:
    """Return the subject UUID if the token is valid and of the expected type, else None."""
    if not token:
        return None
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm], options={"require": ["exp", "sub", "typ"]})
        if payload.get("typ") != expected_type:
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        return None
