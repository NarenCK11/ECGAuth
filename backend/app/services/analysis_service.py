"""Deterministic ECG analysis profile and the unified analysis response.

`build_profile_data` is a pure function of the uploaded recording: the same files always yield
the same profile, byte for byte. Nothing here uses unseeded randomness or the clock.

What is real and what is demonstration data (the UI shows these labels):
  * waveforms, baseline-corrected and z-score signals, R-peaks, heart rate, mean beat -
    computed from the recording;
  * the 128-D embedding - computed by the existing pre-trained CNN feature extractor when
    the model is available (otherwise a hash-seeded placeholder, flagged as such);
  * per-stage timings - *demonstration* values derived deterministically from the file digests.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np

from app.ml import preprocessing
from app.services.ecg_service import ParsedECG

PIPELINE_VERSION = "ecgauth-pipeline-1.0"
MAX_VIEW_SECONDS = 10
MAX_TRACE_POINTS = 1200

# Shown on analyses decided by exact enrolled-file comparison (application accounts).
HASH_VERIFICATION_METRIC = {
    "key": "verification", "label": "Verification method",
    "value": "Exact enrolled-file match (SHA-256)", "unit": "", "kind": "measured",
}

STAGE_DEFS = [
    # id, label, description
    ("acquisition", "Signal Acquisition", "WFDB header and signal files read and validated"),
    ("preprocessing", "Preprocessing", "Baseline wander removed with a moving-average high-pass"),
    ("normalization", "Normalization", "z-score normalisation of the 1500-sample analysis window"),
    ("segmentation", "Segmentation", "R-peaks located; beats aligned and averaged"),
    ("features", "Feature Extraction", "128-dimensional embedding from the CNN feature extractor"),
    ("identity", "Identity Analysis", "Recording compared with the enrolled credential"),
    ("authentication", "Authentication", "Server-side access decision"),
]

# (min_ms, max_ms) demonstration ranges per stage
TIMING_RANGES = {
    "acquisition": (3, 7), "preprocessing": (5, 12), "normalization": (1, 3), "segmentation": (4, 9),
    "features": (14, 30), "identity": (3, 8), "authentication": (1, 3),
}


def _rng(hea_hash: str, dat_hash: str, salt: str) -> np.random.Generator:
    digest = hashlib.sha256(f"{PIPELINE_VERSION}|{salt}|{hea_hash}|{dat_hash}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


def _r(a: np.ndarray, nd: int = 4) -> list[float]:
    return [round(float(x), nd) for x in a]


def _moving_average(x: np.ndarray, win: int) -> np.ndarray:
    win = max(3, win | 1)
    pad = win // 2
    xp = np.pad(x, pad, mode="edge")
    c = np.cumsum(np.insert(xp, 0, 0.0))
    return (c[win:] - c[:-win]) / win


def _detect_r_peaks(x: np.ndarray, fs: float) -> np.ndarray:
    """Greedy amplitude-ordered peak picking with a 250 ms refractory period."""
    z = (x - np.median(x)) / (np.std(x) or 1.0)
    if abs(z.min()) > abs(z.max()):
        z = -z
    thr = max(1.0, 0.5 * float(z.max()))  # half the strongest peak: rejects P/T waves
    interior = np.where((z[1:-1] > z[:-2]) & (z[1:-1] >= z[2:]) & (z[1:-1] > thr))[0] + 1
    order = interior[np.argsort(-z[interior], kind="stable")]
    refractory = int(0.25 * fs)
    taken: list[int] = []
    for i in order:
        if all(abs(int(i) - j) >= refractory for j in taken):
            taken.append(int(i))
    return np.array(sorted(taken), dtype=int)


def build_profile_data(parsed: ParsedECG, hea_hash: str, dat_hash: str, embedding: np.ndarray | None = None) -> dict[str, Any]:
    """Return {signal_data, processed_signal_data, feature_data, stage_data, display_metrics}."""
    fs = parsed.fs
    sig = parsed.signal
    win = preprocessing.WIN_SIZE
    view_n = int(min(sig.size, max(win, MAX_VIEW_SECONDS * fs)))
    view = sig[:view_n]
    step = max(1, math.ceil(view_n / MAX_TRACE_POINTS))
    idx = np.arange(0, view_n, step)

    # --- raw ---------------------------------------------------------------------------------
    signal_data = {
        "fs": fs, "units": parsed.units, "samples_total": int(sig.size), "view_samples": view_n, "decimation": step,
        "t": _r(idx / fs), "v": _r(view[idx]),
        "segment": {"start_idx": 0, "end_idx": win, "start_s": 0.0, "end_s": round(win / fs, 4)},
    }

    # --- processed ---------------------------------------------------------------------------
    baseline = _moving_average(view, int(0.6 * fs))
    filtered = view - baseline
    seg_idx = np.arange(0, win, step)
    normalized = preprocessing.zscore(sig[:win])  # identical to the model's preprocessing
    processed_signal_data = {
        "filtered": {"t": _r(idx / fs), "v": _r(filtered[idx])},
        "normalized": {"t": _r(seg_idx / fs), "v": _r(normalized[seg_idx])},
        "method": {"filtered": "moving-average high-pass (0.6 s), display only",
                   "normalized": "z-score of the first 1500 samples (as used by the model)"},
    }

    # --- segmentation ------------------------------------------------------------------------
    peaks = _detect_r_peaks(filtered, fs)
    hr = None
    if peaks.size >= 2:
        rr = np.diff(peaks) / fs
        hr = float(60.0 / np.median(rr))
    pre, post = int(0.25 * fs), int(0.45 * fs)
    beats = [filtered[p - pre : p + post] for p in peaks if p - pre >= 0 and p + post <= view_n]
    if beats:
        mean_beat = np.mean(np.stack(beats), axis=0)
        bstep = max(1, math.ceil(mean_beat.size / 160))
        bi = np.arange(0, mean_beat.size, bstep)
        mean_beat_data = {"t": _r((bi - pre) / fs), "v": _r(mean_beat[bi]), "beats_averaged": len(beats)}
    else:
        mean_beat_data = {"t": [], "v": [], "beats_averaged": 0}
    beats_in_window = int(np.sum(peaks < win))

    # --- features ----------------------------------------------------------------------------
    if embedding is not None:
        emb, source = np.asarray(embedding, dtype=float).ravel(), "cnn_feature_extractor"
    else:
        emb, source = _rng(hea_hash, dat_hash, "embedding").normal(0, 1, 128), "deterministic_placeholder"
    feature_data = {
        "embedding": _r(emb, 3), "dimension": int(emb.size), "source": source,
        "mean_beat": mean_beat_data,
        "r_peaks_s": _r(peaks / fs),
        "stats": {"l2_norm": round(float(np.linalg.norm(emb)), 3), "mean": round(float(emb.mean()), 4),
                  "std": round(float(emb.std()), 4)},
    }

    # --- stages (timings are demonstration values) -------------------------------------------
    trng = _rng(hea_hash, dat_hash, "timings")
    details = {
        "acquisition": f"{sig.size} samples at {fs:g} Hz ({sig.size / fs:.1f} s)",
        "preprocessing": f"{view_n} samples high-pass filtered",
        "normalization": f"window 0-{win} samples, mean 0, std 1",
        "segmentation": f"{peaks.size} R-peaks detected" + (f", {len(beats)} beats averaged" if beats else ""),
        "features": f"{emb.size}-D embedding ({'pre-trained CNN' if source == 'cnn_feature_extractor' else 'placeholder'})",
        "identity": "Awaiting comparison",
        "authentication": "Awaiting decision",
    }
    stages, total = [], 0
    for sid, label, desc in STAGE_DEFS:
        lo, hi = TIMING_RANGES[sid]
        ms = int(trng.integers(lo, hi + 1))
        total += ms
        stages.append({"id": sid, "label": label, "description": desc, "detail": details[sid],
                       "duration_ms": ms, "timing_kind": "demonstration"})

    # --- display metrics ---------------------------------------------------------------------
    metrics = [
        {"key": "sampling_rate", "label": "Sampling rate", "value": round(fs, 2), "unit": "Hz", "kind": "measured"},
        {"key": "duration", "label": "Recording length", "value": round(sig.size / fs, 2), "unit": "s", "kind": "measured"},
        {"key": "beats", "label": "R-peaks detected", "value": int(peaks.size), "unit": "", "kind": "derived"},
        {"key": "beats_window", "label": "Beats in analysis window", "value": beats_in_window, "unit": "", "kind": "derived"},
    ]
    if hr is not None:
        metrics.append({"key": "heart_rate", "label": "Heart rate", "value": round(hr, 1), "unit": "bpm", "kind": "derived"})
    metrics.append({"key": "stage_timing_total", "label": "Pipeline stage time", "value": total, "unit": "ms",
                    "kind": "demonstration"})

    return {
        "signal_data": signal_data,
        "processed_signal_data": processed_signal_data,
        "feature_data": feature_data,
        "stage_data": {"stages": stages, "total_ms": total},
        "display_metrics": {"metrics": metrics},
    }


def build_analysis_response(
    profile: dict[str, Any],
    *,
    source: str,
    authenticated: bool,
    method: str,
    message: str,
    identity: dict | None,
    identity_detail: str | None = None,
    extra_metrics: list[dict] | None = None,
    processing_time_ms: int | None = None,
) -> dict[str, Any]:
    """The single analysis shape the frontend consumes, whatever path produced the decision."""
    outcome = "completed" if authenticated else "failed"
    stages = []
    for s in profile["stage_data"]["stages"]:
        s = dict(s)
        s["status"] = "completed"
        if s["id"] == "identity":
            # What this stage really does differs by path; say so (also for profiles stored earlier).
            s["description"] = (
                "SVM scores the embedding against the 90 pre-trained identities" if method == "ecg_model"
                else "Exact SHA-256 comparison of the uploaded files with the enrolled ECG files"
            )
            s["status"] = outcome
            s["detail"] = identity_detail or (
                "Recording matches the enrolled credential" if authenticated else "Recording does not match the enrolled credential"
            )
        elif s["id"] == "authentication":
            s["status"] = outcome
            s["detail"] = "Access granted" if authenticated else "Access denied"
        stages.append(s)
    metrics = list(profile["display_metrics"]["metrics"]) + list(extra_metrics or [])
    if processing_time_ms is not None:
        metrics.append({"key": "processing_time", "label": "Server processing time", "value": processing_time_ms,
                        "unit": "ms", "kind": "measured"})
    return {
        "pipeline_version": PIPELINE_VERSION,
        "source": source,  # "enrolled_profile" | "uploaded_file"
        "signal": profile["signal_data"],
        "processed": profile["processed_signal_data"],
        "features": profile["feature_data"],
        "stages": stages,
        "total_stage_ms": profile["stage_data"]["total_ms"],
        "metrics": metrics,
        "authentication": {"authenticated": authenticated, "method": method, "message": message, "identity": identity},
    }
