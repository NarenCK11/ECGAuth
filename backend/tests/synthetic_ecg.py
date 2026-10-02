"""Deterministic synthetic ECG records in WFDB (.hea + .dat) format.

Used by tests and the seed script so that no real patient data is needed.
The same seed always produces byte-identical files.
"""
from __future__ import annotations

import os
import shutil
import tempfile

import numpy as np

FS = 360
N_SAMPLES = 3600  # 10 s


def make_signal(seed: int, n: int = N_SAMPLES, fs: int = FS) -> np.ndarray:
    """Seeded ECG-like trace in millivolts (P-QRS-T beats + baseline wander + noise)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / fs
    hr = 60 + (seed * 7) % 35                    # beats/min, varies per seed
    period = 60.0 / hr
    sig = np.zeros(n)
    for centre in np.arange(0.3, t[-1] + period, period):
        for amp, off, width in (
            (0.15, -0.20, 0.025),                # P
            (-0.12, -0.04, 0.010),               # Q
            (1.00 + 0.05 * (seed % 5), 0.0, 0.012),  # R
            (-0.25, 0.04, 0.012),                # S
            (0.30, 0.25, 0.045),                 # T
        ):
            sig += amp * np.exp(-0.5 * ((t - centre - off) / width) ** 2)
    sig += 0.05 * np.sin(2 * np.pi * 0.25 * t + seed)
    sig += rng.normal(0, 0.01, n)
    return sig


def write_record(directory: str, name: str, seed: int) -> tuple[str, str]:
    """Write ``name.hea`` + ``name.dat`` into *directory*; return their paths."""
    import wfdb

    sig = make_signal(seed).reshape(-1, 1)
    # wrsamp writes into the cwd-relative write_dir; use a scratch dir for determinism
    wfdb.wrsamp(
        name,
        fs=FS,
        units=["mV"],
        sig_name=["MLII"],
        p_signal=sig,
        fmt=["16"],
        write_dir=directory,
    )
    return os.path.join(directory, f"{name}.hea"), os.path.join(directory, f"{name}.dat")


def record_bytes(name: str, seed: int) -> tuple[bytes, bytes]:
    """Return (hea_bytes, dat_bytes) for a synthetic record."""
    tmp = tempfile.mkdtemp(prefix="synecg_")
    try:
        hea, dat = write_record(tmp, name, seed)
        with open(hea, "rb") as f:
            hb = f.read()
        with open(dat, "rb") as f:
            db = f.read()
        return hb, db
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
