# ECGAuth

ECG-based patient authentication with a medical portal and an administration console.

Patients register, enroll a WFDB ECG recording (`.hea` + `.dat`), and later sign in by uploading that recording. The server decides; on success the patient enters a portal showing their (fictional) medical records and authentication history. The browser also shows the ECG moving through an analysis pipeline, with an interactive waveform.

> **Demonstration environment.** All patients, records, doctors and reports are fictional sample data. This is not a real medical-record system.

```
Browser (React + TypeScript)
   │  same-origin /api, HttpOnly session cookies
   ▼
FastAPI ──────────────► MySQL 8  (users, enrollments, analysis profiles, attempts, records, audit)
   │
   └─► ECGModelService ─► existing CNN → random projection → scaler → SVM (unchanged artifacts)
```

## Quick start (Docker)

Requires Docker with Compose.

```bash
cp .env.example .env        # then edit: set passwords, JWT_SECRET, ADMIN_USERNAME/ADMIN_PASSWORD
docker compose up --build
```

Open <http://localhost:8080>. On first start the backend applies migrations and (with `SEED_DEMO=true`) loads demo data and writes the demo patients' ECG files to `./demo_ecg/`.

- Use URL-safe characters (letters/digits) in `MYSQL_PASSWORD`.
- `JWT_SECRET` must be 32+ characters: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- **Model files:** the trained artifacts are git-ignored (see [Model artifacts](#model-artifacts)). They must be present in `backend/app/ml/artifacts/` *before* `docker compose build`.
- On Linux, if the seed cannot write `./demo_ecg`, run `chmod 777 demo_ecg` (container user is uid 10001).

> The Docker setup was validated with `docker compose config` only; the images were not built in the development environment (no Docker daemon was available). The non-Docker path below is what was exercised end to end.

## Local development (no Docker)

Prerequisites: Python 3.11, Node 20+, MySQL 8.

1. **Database.** As a MySQL admin:
   ```sql
   CREATE DATABASE ecgauth      CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE DATABASE ecgauth_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;   -- for the test-suite
   CREATE USER 'ecgauth'@'localhost' IDENTIFIED BY 'choose-a-password';
   GRANT ALL PRIVILEGES ON ecgauth.*      TO 'ecgauth'@'localhost';
   GRANT ALL PRIVILEGES ON ecgauth_test.* TO 'ecgauth'@'localhost';
   ```
2. **Configuration.** `cp .env.example .env` and set `DATABASE_URL`, `TEST_DATABASE_URL`, `JWT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` (10+ characters).
3. **Backend.**
   ```bash
   python -m venv venv && venv\Scripts\activate          # Windows;  source venv/bin/activate elsewhere
   pip install -r backend/requirements-dev.txt
   cd backend
   alembic upgrade head          # create the schema
   python -m app.seed            # demo data (idempotent; add --reset to wipe everything first)
   uvicorn app.main:app --port 8000
   ```
4. **Frontend.**
   ```bash
   cd frontend && npm install && npm run dev      # http://localhost:5173, proxies /api to :8000
   ```

Interactive API docs: <http://localhost:8000/docs>.

### Model artifacts

The pre-trained model files are listed in `.gitignore` and are **not in the repository**. Place these in `backend/app/ml/artifacts/`:

`feature_model.onnx`, `rp_transformer_all.joblib`, `scaler_all.joblib`, `svm_classifier_all.joblib`, `user_mapping.json` (the mapping is committed).

The Python pins (`numpy==1.24.3`, `scikit-learn==1.2.2`, `joblib==1.3.1`, `onnxruntime==1.16.0`) must not be changed: the `.joblib` files are only guaranteed to load under the versions that wrote them. Without the artifacts the API still runs; the model endpoint answers 503 and analyses use a labelled placeholder embedding.

## Demo walkthrough

After seeding, `demo_ecg/` contains `<username>.hea` + `<username>.dat` for each demo patient:

| Patient ID | Username | Name |
|---|---|---|
| PT-1001 | `naren` | Naren Kumar |
| PT-1002 | `akhil` | Akhil Reddy |
| PT-1003 | `adesh` | Adesh Patil |
| PT-1004 – 1006 | `meera`, `rohan`, `sana` | |

1. Open `/login`, enter `naren` (or `PT-1001`), upload `demo_ecg/naren.hea` and `naren.dat` → watch the analysis → **Enter Medical Portal**.
2. Try `naren` with `akhil`'s files to see a failed authentication.
3. `/register` → `/enroll` creates a new account. Enrollment needs *your own* `.hea` + `.dat` (any single-file WFDB recording of ≥1,500 samples; a given recording can only be enrolled once).
4. `/admin/login` with `ADMIN_USERNAME` / `ADMIN_PASSWORD` from your `.env`.

Seeded authentication history is back-dated demonstration data.

## How it works

**Two authentication paths, one analysis experience**

| | Application accounts (registered users) | Pre-trained model identities |
|---|---|---|
| Endpoint | `POST /api/auth/login` | `POST /api/ecg/analyze` |
| Decision | SHA-256 of **both** uploaded files must equal the enrolled digests (constant-time compare). The ML model is not involved. | The original CNN → RP → scaler → SVM pipeline and decision rule, unchanged. |
| Result | Session cookie → medical portal | Analysis + decision only. **Never** creates a session or grants portal access. |

The enrolled files *are* the credential, so treat them like a password file. Only their digests are stored; the raw files are discarded.

**UUID identity.** Every account has a UUID primary key used for all relationships and authorization. `PT-1042` is a display label only.

**Deterministic analysis.** At enrollment the analysis profile is built once from the recording and stored (`pipeline_version = ecgauth-pipeline-1.0`); every later sign-in reuses it, so the visualization is identical each time. It is a pure function of the file bytes (no unseeded randomness, no clock).

What is real and what is demonstration (the UI labels these):

- *Measured/derived from the recording:* waveforms, baseline-corrected and z-score signals, R-peaks, heart rate, averaged beat.
- *From the existing model:* the 128-D embedding (pre-trained CNN feature extractor).
- *Demonstration values:* per-stage timings and their total. The “processing time” in the summary is the real server time for that request.

**A failed login never shows enrolled data.** On failure the analysis is built from the *uploaded* recording, so knowing a username reveals nothing about that user's ECG.

## API

Cookies: patients `ecgauth_session`, administrators `ecgauth_admin` (separate, `HttpOnly`, `SameSite=Lax`, short-lived), registration `ecgauth_enroll`.

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /api/auth/register` | – | Create account (JSON); starts a short enrollment session |
| `POST /api/auth/enroll` | enrollment session | Upload `.hea` + `.dat`; activates the account |
| `POST /api/auth/login` | – | `username` (or `PT-…`) + `.hea` + `.dat`; 200 with session, or 401 with the analysis of the upload |
| `POST /api/auth/logout`, `GET /api/auth/me` | patient | Session |
| `POST /api/ecg/analyze` | – | Model-identity analysis (legacy behaviour) |
| `GET /api/ecg/history`, `GET /api/ecg/{id}` | patient | Own authentication events and their analysis |
| `GET /api/users/me` | patient | Profile and enrollment |
| `GET /api/medical-records`, `/{id}` | patient | Own records only (404 for anyone else's) |
| `POST /api/admin/login`, `/logout`, `GET /api/admin/me` | – / admin | Admin session |
| `GET /api/admin/dashboard`, `/analytics` | admin | Totals, trends, system activity |
| `GET /api/admin/users`, `/users/{id}` · `PATCH /users/{id}/status` | admin | Search, detail, activate/deactivate |
| `GET /api/admin/authentication-events` | admin | Filter by user, date range, result |
| `GET /api/admin/audit-logs` | admin | Security audit trail |
| `GET /api/health` | – | Liveness and ML availability |

## Security notes

- Server-side decisions only; the frontend renders what the API returns. Roles are enforced per request and accounts are re-checked in the database each time, so deactivation takes effect immediately.
- Admin passwords: bcrypt. Credentials come from environment variables (admin created on first start; an existing admin is never modified). Nothing secret is committed; `.env` is git-ignored.
- Uploads: extension, size (client-side cap + early `Content-Length` check + nginx limit), header parsing that rejects path tricks, temp files always removed. Raw ECG files are never stored or served.
- Throttling: 5 failed attempts per username+IP (patients) or per IP (admin) in 15 minutes returns 429. Unknown usernames and wrong ECGs are indistinguishable to the caller.
- Cookies are `HttpOnly` and `SameSite=Lax`; set `COOKIE_SECURE=true` behind HTTPS. Serving UI and API from one origin (Vite proxy / nginx) avoids CORS and cross-site cookie issues.
- All DB access goes through SQLAlchemy (parameterised). Every register/enroll/login/admin action is audit-logged.

## Tests

```bash
cd backend && pytest        # 55 tests; needs TEST_DATABASE_URL (a database ending in _test)
cd frontend && npm run typecheck
```

- `test_ml_regression.py` checks the refactored model adapter against outputs captured from the **original Flask code** (`tests/fixtures/ml_baseline.json`): features, all 90 class scores, decisions, identity mapping.
- `test_api.py` runs the registration → enrollment → login → portal and admin journeys against real MySQL.

## Project layout

```
backend/app/{api,core,models,schemas,services,ml}   FastAPI app (ml/ wraps the unchanged model)
backend/migrations                                  Alembic
backend/app/seed.py                                 python -m app.seed
frontend/src/{pages,components,lib}                 React + TypeScript (custom SVG charts)
legacy/flask_demo                                   The original Flask app, kept for reference (not runnable as-is)
docs/AUDIT.md                                       Pre-refactor repository audit
```

## Known limitations

- **File-hash authentication is a credential, not biometric matching.** Any copy of the enrolled files signs in. This is the specified design for application accounts; protect the files accordingly.
- The model's “similarity” is a softmax over raw SVM margins (the SVC was trained without probability calibration), and its decision rule accepts a top-1 match *or* ≥ 70 %. Both are preserved from the original and are not calibrated confidence.
- The pre-trained identities are the names in `user_mapping.json` (not `person_01…person_90`).
- Throttling keys on the client IP; behind a proxy, make sure the real IP is forwarded.
- No Appointments page (the brief's nav lists it, its page list does not).
