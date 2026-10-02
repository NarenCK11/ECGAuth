"""The refactored ML adapter must reproduce the original Flask pipeline exactly.

`fixtures/ml_baseline.json` was captured from the unmodified legacy `app.py`.
"""
import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

from app.core.config import get_settings
from app.ml import preprocessing
from app.ml.inference import THRESHOLD
from app.services.ml_service import ECGModelService
from tests.synthetic_ecg import write_record

BASELINE = json.loads((Path(__file__).parent / "fixtures" / "ml_baseline.json").read_text())


@pytest.fixture(scope="module")
def ml():
    svc = ECGModelService(get_settings().model_dir)
    assert svc.load_model(), svc.load_error
    return svc


def _window(seed: int) -> np.ndarray:
    import wfdb

    with tempfile.TemporaryDirectory() as d:
        write_record(d, f"rec{seed}", seed)
        rec = wfdb.rdrecord(os.path.join(d, f"rec{seed}"))
    return preprocessing.select_window(np.asarray(rec.p_signal[:, 0]))


def test_constants_unchanged():
    assert preprocessing.WIN_SIZE == BASELINE["win_size"] == 1500
    assert THRESHOLD == BASELINE["threshold"] == 0.70


def test_identity_mapping_unchanged(ml):
    assert ml._model.assets.name_to_label == BASELINE["name_to_label"]
    assert len(ml._model.assets.name_to_label) == 90
    assert sorted(ml._model.assets.name_to_label.values()) == list(range(90))


@pytest.mark.parametrize("case", BASELINE["cases"], ids=lambda c: f"seed{c['seed']}")
def test_features_and_scores_match_legacy(ml, case):
    window = _window(case["seed"])
    feat = ml.extract_features(window)
    np.testing.assert_allclose(feat[0], case["feat96"], rtol=1e-5, atol=1e-6)

    classes, probs = ml._model.class_scores(feat)
    np.testing.assert_allclose(probs, case["probs"], rtol=1e-5, atol=1e-8)
    assert int(classes[int(np.argmax(probs))]) == case["top_label"]


@pytest.mark.parametrize("case", BASELINE["cases"], ids=lambda c: f"seed{c['seed']}")
def test_claiming_the_top_identity_authenticates(ml, case):
    window = _window(case["seed"])
    pred = ml.predict(window, case["top_name"])
    assert pred.authenticated is True
    assert pred.predicted_label == case["top_label"]
    assert pred.predicted_name == case["top_name"]
    assert pred.similarity == pytest.approx(case["probs"][case["top_label"]], rel=1e-5)


def test_case_insensitive_claim_and_unknown_claim(ml):
    window = _window(1)
    top = BASELINE["cases"][0]["top_name"]
    assert ml.predict(window, top.lower()).claimed_label == BASELINE["name_to_label"][top]
    unknown = ml.predict(window, "nobody-here")
    assert unknown.authenticated is False and unknown.similarity is None


def test_all_90_identities_are_scored(ml):
    probs = ml._model.class_scores(ml.extract_features(_window(2)))[1]
    assert probs.shape == (90,) and probs.sum() == pytest.approx(1.0, abs=1e-6)
