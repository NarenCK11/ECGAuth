import asyncio
import io
import json

import pytest

from app.ml.inference import ExistingECGModel
from app.services import analysis_service as an
from app.services.ecg_service import ECGValidationError, UploadedECG, parse_ecg, read_upload
from tests.synthetic_ecg import make_signal, record_bytes


def _upload(seed: int, name: str | None = None) -> UploadedECG:
    from app.core.security import sha256_hex

    name = name or f"rec{seed}"
    hea, dat = record_bytes(name, seed)
    return UploadedECG(hea, dat, f"{name}.hea", f"{name}.dat", sha256_hex(hea), sha256_hex(dat))


def test_parse_valid_record():
    p = parse_ecg(_upload(1))
    assert p.fs == 360 and p.signal.size == 3600
    # wfdb round-trips through 16-bit ADC units, so compare loosely against the source signal
    assert abs(p.signal[100] - make_signal(1)[100]) < 0.01


def test_profile_is_deterministic():
    up = _upload(2)
    a = an.build_profile_data(parse_ecg(up), up.hea_hash, up.dat_hash)
    b = an.build_profile_data(parse_ecg(up), up.hea_hash, up.dat_hash)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_profile_differs_between_recordings():
    u1, u2 = _upload(1), _upload(3)
    a = an.build_profile_data(parse_ecg(u1), u1.hea_hash, u1.dat_hash)
    b = an.build_profile_data(parse_ecg(u2), u2.hea_hash, u2.dat_hash)
    assert a["signal_data"]["v"] != b["signal_data"]["v"]
    assert a["stage_data"]["stages"] != b["stage_data"]["stages"]


def test_profile_content_is_sensible():
    up = _upload(1)  # seed 1 -> 67 bpm in the synthetic generator
    prof = an.build_profile_data(parse_ecg(up), up.hea_hash, up.dat_hash)
    metrics = {m["key"]: m for m in prof["display_metrics"]["metrics"]}
    assert 60 <= metrics["heart_rate"]["value"] <= 75
    assert metrics["stage_timing_total"]["kind"] == "demonstration"
    assert len(prof["signal_data"]["t"]) == len(prof["signal_data"]["v"]) <= 1200
    assert len(prof["processed_signal_data"]["normalized"]["v"]) > 0
    assert len(prof["feature_data"]["embedding"]) == 128
    assert prof["feature_data"]["source"] == "deterministic_placeholder"
    assert [s["id"] for s in prof["stage_data"]["stages"]] == [d[0] for d in an.STAGE_DEFS]


def test_embedding_from_existing_model_is_used_and_stable():
    from app.core.config import get_settings

    model = ExistingECGModel(get_settings().model_dir)
    model.load()
    up = _upload(4)
    parsed = parse_ecg(up)
    emb = model.embedding128(parsed.signal[:1500])
    a = an.build_profile_data(parsed, up.hea_hash, up.dat_hash, emb)
    assert a["feature_data"]["source"] == "cnn_feature_extractor"
    b = an.build_profile_data(parsed, up.hea_hash, up.dat_hash, model.embedding128(parsed.signal[:1500]))
    assert a["feature_data"]["embedding"] == b["feature_data"]["embedding"]


def test_response_marks_failure_without_identity():
    up = _upload(1)
    prof = an.build_profile_data(parse_ecg(up), up.hea_hash, up.dat_hash)
    ok = an.build_analysis_response(prof, source="enrolled_profile", authenticated=True, method="ecg_hash",
                                    message="ok", identity={"patient_id": "PT-1001", "name": "A"})
    bad = an.build_analysis_response(prof, source="uploaded_file", authenticated=False, method="ecg_hash",
                                     message="Authentication failed", identity=None)
    assert all(s["status"] == "completed" for s in ok["stages"])
    assert [s["status"] for s in bad["stages"]][-2:] == ["failed", "failed"]
    assert bad["authentication"]["identity"] is None


# --- validation -------------------------------------------------------------------------------
class _F:
    def __init__(self, name, data):
        self.filename, self._b = name, io.BytesIO(data)

    async def read(self, n=-1):
        return self._b.read(n)


def _read(hea, dat, limit=5_000_000):
    return asyncio.run(read_upload(hea, dat, limit))


def test_upload_rejects_wrong_extension_empty_and_oversize():
    hea, dat = record_bytes("rec1", 1)
    with pytest.raises(ECGValidationError):
        _read(_F("a.txt", hea), _F("a.dat", dat))
    with pytest.raises(ECGValidationError):
        _read(_F("a.hea", b""), _F("a.dat", dat))
    with pytest.raises(ECGValidationError):
        _read(_F("a.hea", hea), _F("a.dat", dat), limit=100)
    with pytest.raises(ECGValidationError):
        _read(None, _F("a.dat", dat))


def test_header_with_path_traversal_is_rejected():
    up = _upload(1)
    evil = up.hea_bytes.replace(b"rec1.dat", b"../../secret.dat")
    assert evil != up.hea_bytes
    bad = UploadedECG(evil, up.dat_bytes, "x.hea", "x.dat", "0" * 64, "0" * 64)
    with pytest.raises(ECGValidationError):
        parse_ecg(bad)


def test_garbage_and_truncated_signal_rejected():
    up = _upload(1)
    with pytest.raises(ECGValidationError):
        parse_ecg(UploadedECG(b"not a header", up.dat_bytes, "x.hea", "x.dat", "0" * 64, "0" * 64))
    with pytest.raises(ECGValidationError):
        parse_ecg(UploadedECG(up.hea_bytes, up.dat_bytes[:1000], "x.hea", "x.dat", "0" * 64, "0" * 64))
