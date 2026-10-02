"""Existing CNN -> RP -> scaler -> SVM inference, moved verbatim from the Flask app.

`ExistingECGModel` is the adapter around the untouched trained artifacts. The only
changes from the original are structural (module-level globals became instance state).
"""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from app.ml import preprocessing
from app.ml.model_loader import ModelAssets, load_model_assets

THRESHOLD = 0.70  # similarity threshold (for claimed user prob)


def softmax(vec: np.ndarray) -> np.ndarray:
    v = np.asarray(vec, dtype=float)
    v = v - np.max(v)
    e = np.exp(v)
    return e / (np.sum(e) + 1e-12)


def _to_int_or_same(v):
    try:
        return int(v)
    except Exception:
        return v


def _find_claim_idx(classes, claimed_label):
    """Return index of claimed_label inside classes; handles type differences."""
    try:
        if claimed_label in classes:
            return int(np.where(classes == claimed_label)[0][0])
        classes_str = np.array(list(map(str, classes)))
        hit = np.where(classes_str == str(claimed_label))[0]
        if hit.size > 0:
            return int(hit[0])
    except Exception:
        pass
    return None


@dataclass
class Prediction:
    authenticated: bool
    predicted_name: str
    predicted_label: object
    similarity: Optional[float]
    threshold: float
    claimed_name: str
    claimed_label: object
    claim_idx: Optional[int]
    probs: np.ndarray = field(repr=False, default=None)
    features: np.ndarray = field(repr=False, default=None)


class ExistingECGModel:
    def __init__(self, model_dir):
        self._model_dir = model_dir
        self._assets: ModelAssets | None = None

    # -- lifecycle ---------------------------------------------------------
    def load(self) -> None:
        self._assets = load_model_assets(self._model_dir)

    @property
    def loaded(self) -> bool:
        return self._assets is not None

    @property
    def assets(self) -> ModelAssets:
        if self._assets is None:
            raise RuntimeError("ECG model is not loaded")
        return self._assets

    # -- pipeline ----------------------------------------------------------
    def preprocess(self, signal: np.ndarray) -> np.ndarray:
        """Window -> z-score. Returns the (1500,) normalised signal."""
        return preprocessing.zscore(signal)

    def extract_features(self, signal: np.ndarray) -> np.ndarray:
        """z-score -> ONNX (128D) -> RP (96D) -> Scaler. Returns shape (1, 96)."""
        a = self.assets
        w_norm = self.preprocess(signal)
        onnx_in = w_norm.reshape(1, preprocessing.WIN_SIZE, 1).astype(np.float32)
        in_name = a.ort_session.get_inputs()[0].name
        out_name = a.ort_session.get_outputs()[0].name
        feat128 = a.ort_session.run([out_name], {in_name: onnx_in})[0]  # (1, 128)
        feat96 = a.rp.transform(feat128)                                 # (1, 96)
        return a.scaler.transform(feat96)                                # (1, 96)

    def embedding128(self, signal: np.ndarray) -> np.ndarray:
        """Raw 128-D CNN embedding (used only for visualisation)."""
        a = self.assets
        onnx_in = self.preprocess(signal).reshape(1, preprocessing.WIN_SIZE, 1).astype(np.float32)
        in_name = a.ort_session.get_inputs()[0].name
        out_name = a.ort_session.get_outputs()[0].name
        return a.ort_session.run([out_name], {in_name: onnx_in})[0][0]

    def class_scores(self, feat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Per-class scores as the original did: predict_proba, else decision_function+softmax."""
        svm = self.assets.svm
        classes = getattr(svm, "classes_", None)
        if classes is None:
            raise RuntimeError("Model classes_ missing")

        probs = None
        if hasattr(svm, "predict_proba"):
            try:
                probs = svm.predict_proba(feat)[0]
            except Exception:
                probs = None

        if probs is None:
            margins = np.atleast_1d(svm.decision_function(feat))
            if margins.ndim == 1:
                if margins.shape[0] == 1:
                    margins = np.hstack([-margins, margins])
            probs = softmax(margins)
            if probs.ndim == 2:
                probs = probs[0]
        return classes, probs

    def infer(self, signal: np.ndarray, claimed_username: str) -> Prediction:
        """Full original decision: top-1 == claimed OR P(claimed) >= THRESHOLD."""
        a = self.assets
        feat = self.extract_features(signal)
        classes, probs = self.class_scores(feat)

        top_idx = int(np.argmax(probs))
        top_label = _to_int_or_same(classes[top_idx])
        predicted_name = a.label_to_name.get(top_label, f"Person_{top_label}")

        if claimed_username in a.name_to_label:
            claimed_label = a.name_to_label[claimed_username]
        else:
            claimed_label = a.name_to_label_ci.get(claimed_username.lower())

        claim_idx = None
        similarity = None
        if claimed_label is not None:
            claim_idx = _find_claim_idx(classes, claimed_label)
            if claim_idx is not None:
                similarity = float(probs[claim_idx])

        authenticated = False
        if claimed_label is not None:
            try:
                authenticated = int(claimed_label) == int(top_label)
            except Exception:
                authenticated = str(claimed_label) == str(top_label)
            if not authenticated and similarity is not None:
                authenticated = similarity >= THRESHOLD

        return Prediction(
            authenticated=bool(authenticated),
            predicted_name=predicted_name,
            predicted_label=top_label,
            similarity=similarity,
            threshold=THRESHOLD,
            claimed_name=claimed_username,
            claimed_label=claimed_label,
            claim_idx=claim_idx,
            probs=probs,
            features=feat,
        )

    def get_analysis(self, signal: np.ndarray, claimed_username: str) -> dict:
        """Prediction plus waveform arrays for the unified analysis response."""
        pred = self.infer(signal, claimed_username)
        return {
            "prediction": pred,
            "raw_window": signal,
            "normalized_window": self.preprocess(signal),
        }
