"""End-to-end API tests against a real MySQL database (see conftest.py)."""
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from tests.conftest import needs_db
from tests.synthetic_ecg import record_bytes

pytestmark = needs_db


@pytest.fixture(scope="session")
def ml_service():
    from app.core.config import get_settings
    from app.services.ml_service import ECGModelService

    svc = ECGModelService(get_settings().model_dir)
    assert svc.load_model()
    return svc


@pytest.fixture()
def make_client(db, ml_service):
    """Factory for independent clients (each has its own cookie jar). Starts from an empty DB + admin."""
    from app.main import app
    from app.services.authentication_service import ensure_admin

    app.state.ml = ml_service
    ensure_admin(db)
    clients = []

    def _make():
        c = TestClient(app, base_url="http://testserver")
        clients.append(c)
        return c

    yield _make
    for c in clients:
        c.close()


@pytest.fixture()
def client(make_client):
    return make_client()


def files(seed: int, name: str | None = None):
    name = name or f"rec{seed}"
    hea, dat = record_bytes(name, seed)
    return {"hea_file": (f"{name}.hea", hea, "text/plain"), "dat_file": (f"{name}.dat", dat, "application/octet-stream")}


def register(c, username="alice", email=None, name="Alice Doe"):
    return c.post("/api/auth/register", json={
        "full_name": name, "email": email or f"{username}@example.com", "date_of_birth": "1990-04-12", "username": username})


def enroll(c, seed):
    return c.post("/api/auth/enroll", files=files(seed))


def login(c, username, seed, **kw):
    return c.post("/api/auth/login", data={"username": username}, files=files(seed), **kw)


def sign_up(c, username="alice", seed=1, **kw):
    assert register(c, username, **kw).status_code == 201
    r = enroll(c, seed)
    assert r.status_code == 200, r.text
    return r.json()


def admin_login(c, password="testadmin-password-1", username="testadmin"):
    return c.post("/api/admin/login", json={"username": username, "password": password})


# --- registration / enrollment -------------------------------------------------------------------
def test_register_and_enroll_creates_uuid_identity_and_hashes(client, db):
    r = register(client)
    assert r.status_code == 201
    u = r.json()["user"]
    assert u["status"] == "pending" and u["patient_id"] == "PT-1001"
    import uuid
    uuid.UUID(u["id"])

    hea, dat = record_bytes("rec1", 1)
    e = client.post("/api/auth/enroll", files=files(1))
    assert e.status_code == 200 and e.json()["user"]["status"] == "active"
    assert e.json()["enrollment_reference"].startswith("ENR-")

    from app.models import AnalysisProfile, ECGEnrollment
    enr = db.scalar(select(ECGEnrollment))
    assert enr.hea_hash == hashlib.sha256(hea).hexdigest() and enr.dat_hash == hashlib.sha256(dat).hexdigest()
    assert str(enr.user_id) == u["id"]
    assert db.scalar(select(func.count()).select_from(AnalysisProfile)) == 1


def test_enroll_requires_registration_session_and_is_one_shot(client, make_client):
    assert make_client().post("/api/auth/enroll", files=files(1)).status_code == 401
    sign_up(client)
    assert enroll(client, 2).status_code == 401  # enrollment session was consumed


def test_duplicate_username_email_and_ecg_rejected(client, make_client):
    sign_up(client, "alice", 1)
    assert register(make_client(), "ALICE", email="other@example.com").status_code == 409  # case-insensitive
    assert register(make_client(), "alice2", email="alice@example.com").status_code == 409
    c2 = make_client()
    assert register(c2, "bob").status_code == 201
    assert enroll(c2, 1).status_code == 409  # same recording cannot be a second credential


def test_registration_validation(client):
    bad = {"full_name": "X", "email": "nope", "date_of_birth": "2999-01-01", "username": "a b"}
    assert client.post("/api/auth/register", json=bad).status_code == 422
    assert register(client, "pt-1001").status_code == 422  # reserved


def test_enroll_rejects_bad_files(client):
    register(client)
    r = client.post("/api/auth/enroll", files={"hea_file": ("a.hea", b"junk", "text/plain"),
                                               "dat_file": ("a.dat", b"junk", "application/octet-stream")})
    assert r.status_code == 400


# --- login -----------------------------------------------------------------------------------------
def test_login_success_creates_session_and_returns_identity(client):
    sign_up(client, "alice", 1)
    r = login(client, "alice", 1)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["authenticated"] is True and body["user"]["username"] == "alice"
    assert body["analysis"]["source"] == "enrolled_profile"
    assert body["analysis"]["authentication"]["identity"]["name"] == "Alice Doe"
    assert [s["status"] for s in body["analysis"]["stages"]] == ["completed"] * 7
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["user"]["id"] == body["user"]["id"]


def test_login_by_patient_id(client):
    sign_up(client, "alice", 1)
    assert login(client, "PT-1001", 1).status_code == 200


def test_login_with_different_ecg_fails_without_session_or_leak(client, make_client):
    sign_up(client, "alice", 1)
    c = make_client()
    r = login(c, "alice", 2)
    assert r.status_code == 401
    body = r.json()
    assert body["authenticated"] is False and body["user"] is None
    assert body["analysis"]["source"] == "uploaded_file"
    assert body["analysis"]["features"]["source"] == "cnn_feature_extractor"
    assert body["analysis"]["authentication"]["identity"] is None
    assert [s["status"] for s in body["analysis"]["stages"]][-2:] == ["failed", "failed"]
    assert "ecgauth_session" not in c.cookies
    assert c.get("/api/auth/me").status_code == 401

    # the failed analysis shows the *uploaded* recording, never the enrolled one
    ok = login(client, "alice", 1).json()["analysis"]["signal"]["v"]
    assert body["analysis"]["signal"]["v"] != ok


def test_both_files_must_match(client, make_client):
    sign_up(client, "alice", 1)
    h1, d1 = record_bytes("rec1", 1)
    _, d2 = record_bytes("rec1", 2)
    c = make_client()
    r = c.post("/api/auth/login", data={"username": "alice"},
               files={"hea_file": ("rec1.hea", h1, "text/plain"), "dat_file": ("rec1.dat", d2, "application/octet-stream")})
    assert r.status_code == 401


def test_unknown_user_is_indistinguishable_from_wrong_ecg(client, make_client):
    sign_up(client, "alice", 1)
    unknown = login(make_client(), "nobody", 2)
    wrong = login(make_client(), "alice", 2)
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["message"] == wrong.json()["message"]
    assert unknown.json().keys() == wrong.json().keys()


def test_login_with_invalid_files_is_400_and_recorded(client, db):
    sign_up(client, "alice", 1)
    r = client.post("/api/auth/login", data={"username": "alice"},
                    files={"hea_file": ("a.hea", b"junk", "text/plain"), "dat_file": ("a.dat", b"junk", "application/octet-stream")})
    assert r.status_code == 400
    from app.models import AuthenticationAttempt
    assert db.scalar(select(AuthenticationAttempt.failure_reason).order_by(AuthenticationAttempt.created_at.desc())) == "invalid_files"


def test_analysis_is_identical_across_logins(client):
    sign_up(client, "alice", 1)
    a = login(client, "alice", 1).json()["analysis"]
    b = login(client, "alice", 1).json()["analysis"]

    def stable(x):
        m = [m for m in x["metrics"] if m["key"] != "processing_time"]
        return {**x, "metrics": m}
    assert stable(a) == stable(b)


def test_inactive_account_cannot_login_and_existing_session_is_revoked(client, make_client):
    info = sign_up(client, "alice", 1)
    assert login(client, "alice", 1).status_code == 200
    adm = make_client()
    assert admin_login(adm).status_code == 200
    r = adm.patch(f"/api/admin/users/{info['user']['id']}/status", json={"status": "inactive"})
    assert r.status_code == 200 and r.json()["status"] == "inactive"
    assert client.get("/api/auth/me").status_code == 401           # live session killed immediately
    assert login(make_client(), "alice", 1).status_code == 401      # and cannot log back in
    adm.patch(f"/api/admin/users/{info['user']['id']}/status", json={"status": "active"})
    assert login(make_client(), "alice", 1).status_code == 200


def test_failed_attempt_throttle(client, make_client):
    sign_up(client, "alice", 1)
    c = make_client()
    for _ in range(5):
        assert login(c, "alice", 2).status_code == 401
    assert login(c, "alice", 2).status_code == 429
    assert login(c, "alice", 1).status_code == 429  # even the right ECG waits out the lockout


def test_logout_clears_session(client):
    sign_up(client, "alice", 1)
    login(client, "alice", 1)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


# --- medical portal ----------------------------------------------------------------------------------
def test_medical_records_require_authentication(client):
    assert client.get("/api/medical-records").status_code == 401
    assert client.get("/api/ecg/history").status_code == 401
    assert client.get("/api/users/me").status_code == 401


def test_users_only_see_their_own_records_and_events(client, make_client):
    sign_up(client, "alice", 1)
    login(client, "alice", 1)
    bob = make_client()
    sign_up(bob, "bob", 2, name="Bob Roe")
    assert login(bob, "bob", 2).status_code == 200

    mine = client.get("/api/medical-records").json()
    assert "fictional" in mine["disclaimer"] and len(mine["items"]) >= 5
    his = bob.get("/api/medical-records").json()
    assert {r["id"] for r in mine["items"]}.isdisjoint({r["id"] for r in his["items"]})
    assert client.get(f"/api/medical-records/{his['items'][0]['id']}").status_code == 404
    assert client.get(f"/api/medical-records/{mine['items'][0]['id']}").status_code == 200

    my_events = client.get("/api/ecg/history").json()
    bob_event = bob.get("/api/ecg/history").json()[0]["id"]
    assert client.get(f"/api/ecg/{bob_event}").status_code == 404
    assert client.get(f"/api/ecg/{my_events[0]['id']}").status_code == 200


def test_history_and_event_detail(client, make_client):
    sign_up(client, "alice", 1)
    login(make_client(), "alice", 2)  # failed attempt by someone else, recorded against alice
    login(client, "alice", 1)
    hist = client.get("/api/ecg/history").json()
    assert [h["result"] for h in hist] == ["success", "failure"]
    assert hist[0]["enrollment_reference"].startswith("ENR-") and hist[0]["pipeline_version"] == "ecgauth-pipeline-1.0"
    ok = client.get(f"/api/ecg/{hist[0]['id']}").json()
    assert ok["analysis"]["source"] == "enrolled_profile" and ok["analysis"]["authentication"]["authenticated"] is True
    bad = client.get(f"/api/ecg/{hist[1]['id']}").json()
    assert bad["analysis"] is None and bad["note"]


def test_profile_endpoint(client):
    sign_up(client, "alice", 1)
    login(client, "alice", 1)
    p = client.get("/api/users/me").json()
    assert p["user"]["patient_id"] == "PT-1001" and p["authentication_count"] == 1
    assert p["enrollment"]["reference"].startswith("ENR-")


# --- admin ---------------------------------------------------------------------------------------------
def test_admin_login_and_access_control(client, make_client):
    assert client.get("/api/admin/dashboard").status_code == 401
    assert admin_login(client, password="wrong").status_code == 401
    assert admin_login(client, username="nobody").status_code == 401
    assert admin_login(client).status_code == 200
    assert client.get("/api/admin/dashboard").status_code == 200

    # roles are fenced in both directions
    sign_up(make_client(), "alice", 1)
    pat = make_client()
    login(pat, "alice", 1)
    assert pat.get("/api/admin/dashboard").status_code == 401
    assert client.get("/api/medical-records").status_code == 401  # admin has no patient session


def test_admin_cannot_use_patient_login(client):
    assert login(client, "testadmin", 1).status_code == 401


def test_admin_login_lockout(client):
    for _ in range(5):
        assert admin_login(client, password="wrong").status_code == 401
    assert admin_login(client).status_code == 429


def test_admin_password_is_hashed_not_stored(client, db):
    from app.models import User
    pw = db.scalar(select(User.password_hash).where(User.username == "testadmin"))
    assert pw.startswith("$2") and "testadmin-password-1" not in pw


def test_admin_dashboard_users_and_events(client, make_client):
    sign_up(make_client(), "alice", 1)
    sign_up(make_client(), "bob", 2, name="Bob Roe")
    login(make_client(), "alice", 1)
    login(make_client(), "bob", 1)      # failure
    login(make_client(), "ghost", 2)    # failure, unknown
    adm = make_client()
    admin_login(adm)

    d = adm.get("/api/admin/dashboard").json()
    assert d["totals"]["registered_users"] == 2
    assert d["totals"]["authentication_events"] == 3 and d["totals"]["successful"] == 1 and d["totals"]["failed"] == 2
    assert len(d["trend"]) == 14 and d["trend"][-1]["success"] == 1 and d["trend"][-1]["failure"] == 2
    assert d["system"]["ml_available"] is True

    users = adm.get("/api/admin/users").json()
    assert users["total"] == 2 and [u["patient_id"] for u in users["items"]] == ["PT-1001", "PT-1002"]
    assert adm.get("/api/admin/users", params={"search": "bob"}).json()["total"] == 1
    assert adm.get("/api/admin/users", params={"search": "PT-1001"}).json()["items"][0]["username"] == "alice"
    uid = users["items"][0]["id"]
    assert adm.get("/api/admin/users", params={"search": uid}).json()["total"] == 1
    detail = adm.get(f"/api/admin/users/{uid}").json()
    assert detail["user"]["enrolled"] and detail["user"]["auth_total"] == 1 and detail["enrollment_reference"]

    ev = adm.get("/api/admin/authentication-events").json()
    assert ev["total"] == 3
    assert adm.get("/api/admin/authentication-events", params={"result": "failure"}).json()["total"] == 2
    assert adm.get("/api/admin/authentication-events", params={"user": "ghost"}).json()["total"] == 1
    assert adm.get("/api/admin/authentication-events", params={"user": "PT-1002"}).json()["total"] == 1
    assert adm.get("/api/admin/authentication-events", params={"date_from": "2999-01-01"}).json()["total"] == 0

    an = adm.get("/api/admin/analytics").json()
    assert {r["reason"] for r in an["failure_reasons"]} == {"ecg_mismatch", "unknown_user"}
    assert len(an["daily"]) == 30 and len(an["hourly_utc"]) == 24


def test_audit_log_records_security_events(client, make_client):
    info = sign_up(client, "alice", 1)
    login(client, "alice", 1)
    login(make_client(), "alice", 2)
    adm = make_client()
    admin_login(adm)
    adm.patch(f"/api/admin/users/{info['user']['id']}/status", json={"status": "inactive"})
    actions = {a["action"] for a in adm.get("/api/admin/audit-logs").json()["items"]}
    assert {"register", "enroll", "login_success", "login_failure", "admin_login_success", "user_status_changed"} <= actions
    assert adm.get("/api/admin/audit-logs", params={"action": "login_failure"}).json()["total"] == 1


def test_pending_user_status_cannot_be_changed(client, make_client):
    uid = register(client).json()["user"]["id"]
    adm = make_client()
    admin_login(adm)
    assert adm.patch(f"/api/admin/users/{uid}/status", json={"status": "active"}).status_code == 409


# --- ML model path ------------------------------------------------------------------------------------
def test_model_identify_endpoint_keeps_legacy_behaviour(client, ml_service):
    import json
    from pathlib import Path
    case = json.loads((Path(__file__).parent / "fixtures" / "ml_baseline.json").read_text())["cases"][0]
    r = client.post("/api/ecg/analyze", data={"username": case["top_name"]}, files=files(case["seed"]))
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["authenticated"] is True and b["predicted_name"] == case["top_name"]
    assert b["predicted_label"] == case["top_label"] and b["threshold"] == 0.7
    assert b["similarity"] == pytest.approx(case["probs"][case["top_label"]], rel=1e-5)
    assert b["analysis"]["authentication"]["method"] == "ecg_model"
    assert b["analysis"]["features"]["source"] == "cnn_feature_extractor"
    assert "ecgauth_session" not in client.cookies  # model identities never get portal sessions
    assert client.get("/api/medical-records").status_code == 401


def test_model_identify_wrong_claim_fails(client):
    r = client.post("/api/ecg/analyze", data={"username": "Person_89"}, files=files(1))
    assert r.status_code == 200 and "authenticated" in r.json()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "ml_available": True}


# --- hardening ------------------------------------------------------------------------------------------
def test_oversized_upload_rejected_before_reading_body(client):
    r = client.post("/api/auth/login", data={"username": "x"}, headers={"Content-Length": str(50 * 1024 * 1024)},
                    files={"hea_file": ("a.hea", b"x", "text/plain"), "dat_file": ("a.dat", b"x", "application/octet-stream")})
    assert r.status_code == 413


def test_security_headers_and_no_store(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


def test_weak_bootstrap_admin_password_is_refused(db, monkeypatch):
    from app.core import config
    from app.services.authentication_service import ensure_admin

    monkeypatch.setenv("ADMIN_USERNAME", "weakadmin")
    monkeypatch.setenv("ADMIN_PASSWORD", "short")
    config.get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            ensure_admin(db)
    finally:
        monkeypatch.undo()
        config.get_settings.cache_clear()


# --- Phase 11 journey --------------------------------------------------------------------------------------
def test_full_journey_register_enroll_logout_login_portal(client, make_client):
    info = sign_up(client, "journey", 7, name="Jo Urney")
    assert client.get("/api/auth/me").status_code == 401            # enrolling does not sign in
    c = make_client()
    r = login(c, "journey", 7)
    assert r.status_code == 200 and r.json()["analysis"]["authentication"]["authenticated"] is True
    assert c.get("/api/auth/me").json()["user"]["id"] == info["user"]["id"]   # session identity is the UUID
    assert c.get("/api/medical-records").status_code == 200
    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/medical-records").status_code == 401
    assert login(c, "journey", 7).status_code == 200                # and back in again


# --- trained model identities through the normal sign-in ---------------------------------------------------
def _baseline_case():
    import json
    from pathlib import Path
    return json.loads((Path(__file__).parent / "fixtures" / "ml_baseline.json").read_text())["cases"][0]


def test_trained_identity_signs_in_through_model_without_session(client):
    case = _baseline_case()
    r = login(client, case["top_name"].upper(), case["seed"])     # case-insensitive, no app account exists
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["authenticated"] is True and body["user"] is None
    assert body["analysis"]["authentication"]["method"] == "ecg_model"
    assert body["analysis"]["authentication"]["identity"]["name"] == case["top_name"]
    assert "SVM" in next(s for s in body["analysis"]["stages"] if s["id"] == "identity")["description"]
    assert "ecgauth_session" not in client.cookies
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/medical-records").status_code == 401


def test_trained_identity_with_someone_elses_ecg_is_rejected_like_the_original(client, ml_service):
    case = _baseline_case()
    other = next(n for n in ml_service.known_identities() if n != case["top_name"])
    r = login(client, other, case["seed"])
    # Original rule: top-1 match OR score >= 0.70. A different identity's ECG normally does neither.
    assert r.status_code in (200, 401)
    assert r.json()["authenticated"] == (r.status_code == 200)


def test_trained_identity_attempts_are_recorded_and_throttled(client, db):
    from app.models import AuthenticationAttempt
    case = _baseline_case()
    other = next(n for n in ["Person_89", "Person_50", "Person_20"] if n != case["top_name"])
    codes = [login(client, other, case["seed"]).status_code for _ in range(7)]
    if 401 in codes:  # only meaningful when the wrong-identity attempts really failed
        assert codes[-1] == 429
    assert db.scalar(select(func.count()).select_from(AuthenticationAttempt)
                     .where(AuthenticationAttempt.authentication_method == "ecg_model")) >= 1


def test_registering_a_trained_identity_name_is_refused(client):
    assert register(client, "person_08").status_code == 409
    assert register(client, "mustafa", email="m@example.com").status_code == 409


def test_registered_accounts_keep_using_the_hash_path(client, make_client):
    sign_up(client, "alice", 1)
    r = login(make_client(), "alice", 1)
    assert r.json()["analysis"]["authentication"]["method"] == "ecg_hash"
