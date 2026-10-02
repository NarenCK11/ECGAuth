"""Loads the pre-trained artifacts. Nothing here modifies or retrains the model."""
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import joblib
import onnxruntime as ort

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelAssets:
    ort_session: Any
    rp: Any
    scaler: Any
    svm: Any
    name_to_label: dict
    label_to_name: dict
    name_to_label_ci: dict


def load_model_assets(model_dir: str | os.PathLike) -> ModelAssets:
    model_dir = os.fspath(model_dir)
    log.info("Loading models & mapping from %s", model_dir)
    ort_sess = ort.InferenceSession(
        os.path.join(model_dir, "feature_model.onnx"),
        providers=["CPUExecutionProvider"],
    )
    rp = joblib.load(os.path.join(model_dir, "rp_transformer_all.joblib"))
    scaler = joblib.load(os.path.join(model_dir, "scaler_all.joblib"))
    svm = joblib.load(os.path.join(model_dir, "svm_classifier_all.joblib"))
    with open(os.path.join(model_dir, "user_mapping.json"), "r") as f:
        name2label = json.load(f)

    # invert mapping label->name (handle ints stored as strings)
    label2name = {}
    for k, v in name2label.items():
        try:
            v_i = int(v)
        except Exception:
            v_i = v
        label2name[v_i] = k

    # case-insensitive name lookup
    name2label_ci = {k.strip().lower(): v for k, v in name2label.items()}

    log.info("Models loaded successfully.")
    return ModelAssets(ort_sess, rp, scaler, svm, name2label, label2name, name2label_ci)
