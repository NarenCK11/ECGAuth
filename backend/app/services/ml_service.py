"""Service interface in front of the existing ML engine.

The rest of the application talks to this class only; it never imports sklearn/onnx.
Application-level (hash-based) authentication does not depend on it.
"""
import logging
import threading
from pathlib import Path

import numpy as np

from app.ml.inference import ExistingECGModel, Prediction

log = logging.getLogger(__name__)


class ECGModelService:
    def __init__(self, model_dir: Path):
        self._model = ExistingECGModel(model_dir)
        self._lock = threading.Lock()
        self.load_error: str | None = None

    # -- lifecycle ---------------------------------------------------------
    def load_model(self) -> bool:
        """Load artifacts once. Returns availability; never raises (the API stays up without ML)."""
        with self._lock:
            if self._model.loaded:
                return True
            try:
                self._model.load()
                self.load_error = None
            except Exception as e:  # missing artifacts, version mismatch, ...
                self.load_error = str(e)
                log.error("Could not load ECG model assets: %s", e)
        return self._model.loaded

    @property
    def available(self) -> bool:
        return self._model.loaded

    def _require(self) -> None:
        if not self.available and not self.load_model():
            raise RuntimeError(f"ECG model unavailable: {self.load_error}")

    # -- pipeline ----------------------------------------------------------
    def preprocess(self, signal: np.ndarray) -> np.ndarray:
        return self._model.preprocess(signal)

    def extract_features(self, signal: np.ndarray) -> np.ndarray:
        self._require()
        return self._model.extract_features(signal)

    def embedding(self, signal: np.ndarray) -> np.ndarray:
        self._require()
        return self._model.embedding128(signal)

    def predict(self, signal: np.ndarray, claimed_username: str) -> Prediction:
        self._require()
        return self._model.infer(signal, claimed_username)

    def known_identities(self) -> list[str]:
        self._require()
        return sorted(self._model.assets.name_to_label)
