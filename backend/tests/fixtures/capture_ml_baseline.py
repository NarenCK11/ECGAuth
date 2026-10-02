"""Capture the legacy Flask model's outputs for seeded synthetic ECGs.

Run ONCE from the repo root against the original Flask `app.py` (before the
refactor) to produce ``ml_baseline.json``. The regression test then asserts that
the refactored ``ECGModelService`` reproduces these numbers.

    python backend/tests/fixtures/capture_ml_baseline.py <path-to-legacy-app-dir>
"""
import json
import os
import sys
import tempfile

import numpy as np

legacy_dir = os.path.abspath(sys.argv[1])
sys.path.insert(0, legacy_dir)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(legacy_dir)

import wfdb  # noqa: E402

import app as legacy  # noqa: E402  (the original Flask module)
from synthetic_ecg import write_record  # noqa: E402

SEEDS = [1, 2, 3, 4, 5]
out = {"win_size": legacy.WIN_SIZE, "threshold": legacy.THRESHOLD, "cases": []}

for seed in SEEDS:
    with tempfile.TemporaryDirectory() as d:
        write_record(d, f"rec{seed}", seed)
        rec = wfdb.rdrecord(os.path.join(d, f"rec{seed}"))
    sig = np.asarray(rec.p_signal[:, 0])
    window = sig[: legacy.WIN_SIZE]
    feat = legacy.process_signal_window(window)
    # production path: SVC(probability=False) -> decision_function -> softmax
    try:
        probs = legacy.SVM_MODEL.predict_proba(feat)[0]
        path = "predict_proba"
    except Exception:
        margins = np.atleast_1d(legacy.SVM_MODEL.decision_function(feat))
        probs = legacy.softmax(margins)
        probs = probs[0] if probs.ndim == 2 else probs
        path = "decision_function+softmax"
    classes = legacy.SVM_MODEL.classes_
    top = int(np.argmax(probs))
    out["cases"].append({
        "seed": seed,
        "path": path,
        "feat96": feat[0].tolist(),
        "probs": [float(p) for p in probs],
        "top_label": int(classes[top]),
        "top_name": legacy.LABEL_TO_NAME.get(int(classes[top])),
    })

out["name_to_label"] = legacy.NAME_TO_LABEL
dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ml_baseline.json")
with open(dest, "w") as f:
    json.dump(out, f)
print("wrote", dest, "cases:", len(out["cases"]), "path:", out["cases"][0]["path"])
