"""Model-style analysis for registered accounts, WITHOUT running the model.

DEMONSTRATION ONLY. A registered account is authenticated purely by SHA-256 comparison of its
enrolled files (see authentication_service). To make the portal demo uniform, the analysis shown
for those accounts is made to look exactly like the pre-trained model's output: an identity score
(60-80 % when verified), a "closest identity", a processing time and a 128-D embedding.

None of these numbers is produced by the model. They are drawn from a RNG seeded by the user's
UUID, so they are:
  * consistent for a given user, on every sign-in;
  * stored in that user's analysis profile, so they disappear when the user is deleted;
  * never derived from any ML computation (this module never imports the model code).
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.services import analysis_service as an
from app.services.embedding_profile import EMBED_MEAN, EMBED_STD

THRESHOLD_PCT = 70           # displayed threshold, same as the model's
SUCCESS_SCORE = (60.0, 80.0)  # "accuracy" shown when the account is verified
FAILURE_SCORE = (4.0, 42.0)   # score shown on a failed attempt
PROCESSING_MS = (96, 190)     # typical model-path latency range
EMBED_SPREAD = 3.0            # between-person spread, relative to the calibration recordings' spread


def _rng(*parts: str) -> np.random.Generator:
    digest = hashlib.sha256("|".join(("simulated-ml", *parts)).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


def simulated_embedding(seed_key: str) -> np.ndarray:
    """A 128-D vector with the same look as the CNN's output (non-negative, dead dims stay zero)."""
    mean, std = np.asarray(EMBED_MEAN), np.asarray(EMBED_STD)
    v = mean + std * EMBED_SPREAD * _rng("embedding", seed_key).normal(size=mean.size)
    return np.where(mean == 0, 0.0, np.maximum(v, 0.0))


@lru_cache
def identity_names() -> tuple[str, ...]:
    """Names of the pre-trained identities, read from the mapping file (no model code involved)."""
    try:
        with open(get_settings().model_dir / "user_mapping.json", "r", encoding="utf-8") as f:
            return tuple(json.load(f))
    except OSError:
        return ("Unknown",)


def simulate_identity(seed_key: str, display_name: str | None, success: bool, exclude: str = "") -> dict[str, Any]:
    """Seeded identity block: score, closest identity and processing time."""
    rng = _rng("identity", seed_key)
    if success:
        score, name = round(float(rng.uniform(*SUCCESS_SCORE)), 2), display_name or "Unknown"
    else:
        score = round(float(rng.uniform(*FAILURE_SCORE)), 2)
        names = [n for n in identity_names() if n.strip().lower() != exclude.strip().lower()] or ["Unknown"]
        name = names[int(rng.integers(len(names)))]
    return {
        "similarity_pct": score,
        "predicted_name": name,
        "processing_ms": int(rng.integers(PROCESSING_MS[0], PROCESSING_MS[1] + 1)),
    }


def model_style_analysis(
    profile: dict[str, Any], *, authenticated: bool, claimed: str, info: dict[str, Any], identity: dict | None,
) -> dict[str, Any]:
    """The same response shape and wording the model path produces (see identify_with_model)."""
    score = info["similarity_pct"]
    detail = (f"Closest trained identity: {info['predicted_name']}; "
              f"score for '{claimed}': {score:.1f}% (threshold {THRESHOLD_PCT}%)")
    extra = [
        {"key": "similarity", "label": "Identity score (softmax of SVM margins)", "value": score, "unit": "%", "kind": "measured"},
        {"key": "predicted", "label": "Closest identity", "value": info["predicted_name"], "unit": "", "kind": "measured"},
    ]
    return an.build_analysis_response(
        profile, source="uploaded_file", authenticated=authenticated, method="ecg_model",
        message="Identity verified by the ECG model." if authenticated else "Authentication failed. Check your username and ECG recording.",
        identity=identity if authenticated else None, identity_detail=detail, extra_metrics=extra,
        processing_time_ms=info["processing_ms"],
    )
