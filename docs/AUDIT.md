# Phase 1 — Repository Audit

Snapshot of the repository before the FastAPI / PostgreSQL / React refactor.

## What exists

| Area | Finding |
|---|---|
| Backend | Single-file Flask app, `app.py` (~300 lines). Routes: `/`, `/demo`, `/health`, `POST /identify`. |
| Frontend | Server-rendered Jinja templates (`home.html`, `demo.html`, `base.html`) + one vanilla JS file and one CSS file. |
| Persistence | None. No users, no sessions, no history. |
| Tests | None. |
| Deploy config | `Procfile` (gunicorn) and `vercel.json` — both specific to the Flask app. |
| Dependencies | `numpy==1.24.3`, `scikit-learn==1.2.2`, `joblib==1.3.1`, `onnxruntime==1.16.0`, `wfdb==4.1.2`. These pins matter: the `.joblib` files are only guaranteed to unpickle under the sklearn version that wrote them. |

## ML pipeline (must stay bit-for-bit compatible)

```
.hea + .dat --wfdb.rdrecord--> channel 0 --first 1500 samples (WIN_SIZE=1500, STRIDE=1500)
  --> z-score (mean/std of the window; std or 1.0)
  --> reshape (1, 1500, 1) float32
  --> feature_model.onnx          -> (1, 128)
  --> rp_transformer_all.joblib   -> (1, 96)    random projection
  --> scaler_all.joblib           -> (1, 96)    standard scaler
  --> svm_classifier_all.joblib   -> SVC, 90 classes
```

Decision rule in `/identify`: look up claimed username -> label (case-insensitive);
authenticated if `argmax == claimed_label` **or** `P(claimed) >= 0.70`.

Findings worth knowing:

1. **The SVC was trained without `probability=True`.** `predict_proba` raises, so production
   always takes the `decision_function` + softmax fallback. The "similarity" shown to users
   is a softmax over raw SVM margins, not a calibrated probability. Behaviour is preserved
   as-is; the UI must not call it a calibrated confidence.
2. **Identity names do not match the brief.** `user_mapping.json` maps 90 labels (0-89) to
   names such as `John Smith`, `Mustafa`, `Person_08` ... `Person_89`, `Amogh` — not
   `person_01`-`person_90`. The mapping file is authoritative and is left untouched.
3. **The OR rule is permissive** (top-1 match *or* similarity >= 0.70). Preserved because the
   brief says existing behaviour must not change; noted here for the report.
4. Model artifacts (`*.onnx`, `*.joblib`) are listed in `.gitignore` while `.gitattributes`
   marks them as Git LFS. They are therefore **not in version control** and exist only on this
   machine. Docker builds read them from the working tree. Anyone cloning the repo needs the
   artifacts supplied separately (documented in the README).
5. No sample `.hea`/`.dat` files are in the repo. Tests use seeded synthetic WFDB records
   (`backend/tests/synthetic_ecg.py`).
6. Uploaded filenames are passed through `secure_filename`, files are saved to
   `uploads/rec_<uuid>/` and removed afterwards — the cleanup pattern is reused.
7. `app_log.txt` is a committed dev-server log; `app.secret_key` falls back to a hard-coded
   string. Neither carries over.

Model input signature: `['unk__125', 1500, 1] -> ['unk__126', 128]`; SVC has 90 classes.

## Regression safety net

`backend/tests/fixtures/ml_baseline.json` was produced by running the **original, unmodified**
Flask `process_signal_window` + SVM path on five seeded synthetic records (96-D feature vectors,
all 90 class scores, top label). The refactored `ECGModelService` is tested against it.

## Reuse plan

| Existing | Becomes |
|---|---|
| `process_signal_window`, `softmax`, label lookup, rule in `/identify` | `backend/app/ml/` (`model_loader`, `preprocessing`, `inference`) wrapped by `ECGModelService` / `ExistingECGModel` — logic moved verbatim |
| `user_mapping.json`, `*.onnx`, `*.joblib` | `backend/app/ml/artifacts/` (moved, contents unchanged) |
| wfdb read + temp-dir + cleanup pattern | `ecg_service` file validation |
| Flask routes, templates, static, Procfile, vercel.json | Superseded; Flask app archived under `legacy/` |

## Environment notes

Python 3.11.0, Node 20.20, npm 10.8, Docker 27.4 CLI installed (Docker Desktop daemon was not
running at audit time), no local PostgreSQL.
