"""Validation and parsing of uploaded WFDB (.hea + .dat) recordings.

Uploads are untrusted. The header is parsed here *before* wfdb sees it so that a crafted header
cannot make wfdb open files outside the scratch directory. Everything is written to a temporary
directory that is always removed.
"""
import os
import re
import shutil
import tempfile
from dataclasses import dataclass

import numpy as np

from app.core.security import sha256_hex
from app.ml.preprocessing import WIN_SIZE

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
MAX_HEADER_BYTES = 64 * 1024


class ECGValidationError(ValueError):
    """The upload is not a usable WFDB recording. The message is safe to show to the user."""


@dataclass
class UploadedECG:
    hea_bytes: bytes
    dat_bytes: bytes
    hea_filename: str
    dat_filename: str
    hea_hash: str
    dat_hash: str


@dataclass
class ParsedECG:
    signal: np.ndarray  # channel 0, physical units
    fs: float
    units: str


async def read_upload(hea_file, dat_file, max_bytes: int) -> UploadedECG:
    """Read both uploads with a hard size cap and check extensions."""
    out = []
    for f, ext, limit in ((hea_file, ".hea", min(max_bytes, MAX_HEADER_BYTES)), (dat_file, ".dat", max_bytes)):
        if f is None or not f.filename:
            raise ECGValidationError("Please provide both a header (.hea) and a signal (.dat) file.")
        if not f.filename.lower().endswith(ext):
            raise ECGValidationError(f"The {ext} file must have a {ext} extension.")
        data = await f.read(limit + 1)
        if len(data) > limit:
            raise ECGValidationError(f"The {ext} file is too large.")
        if not data:
            raise ECGValidationError(f"The {ext} file is empty.")
        out.append(data)
    hea, dat = out
    return UploadedECG(
        hea_bytes=hea,
        dat_bytes=dat,
        hea_filename=os.path.basename(hea_file.filename)[:255],
        dat_filename=os.path.basename(dat_file.filename)[:255],
        hea_hash=sha256_hex(hea),
        dat_hash=sha256_hex(dat),
    )


def _inspect_header(hea_bytes: bytes) -> tuple[str, str]:
    """Return (record_name, dat_file_name) after rejecting anything unsafe."""
    try:
        text = hea_bytes.decode("ascii")
    except UnicodeDecodeError:
        raise ECGValidationError("The header (.hea) file is not a valid WFDB header.")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if len(lines) < 2:
        raise ECGValidationError("The header (.hea) file is not a valid WFDB header.")
    first = lines[0].split()
    if len(first) < 3 or not SAFE_NAME.match(first[0].split("/")[0]):
        raise ECGValidationError("The header (.hea) file is not a valid WFDB header.")
    nsig = int(first[1]) if first[1].isdigit() else 0
    if nsig < 1 or len(lines) < 1 + nsig:
        raise ECGValidationError("The header (.hea) file is not a valid WFDB header.")
    names = {ln.split()[0] for ln in lines[1 : 1 + nsig]}
    if len(names) != 1:
        raise ECGValidationError("Only recordings stored in a single .dat file are supported.")
    dat_name = names.pop()
    if not SAFE_NAME.match(dat_name):
        raise ECGValidationError("The header (.hea) references an invalid signal file name.")
    return first[0].split("/")[0], dat_name


def parse_ecg(upload: UploadedECG) -> ParsedECG:
    """Fully parse the recording with wfdb (channel 0). Raises ECGValidationError if unusable."""
    record_name, dat_name = _inspect_header(upload.hea_bytes)
    tmp = tempfile.mkdtemp(prefix="ecgauth_")
    try:
        base = os.path.join(tmp, "rec")
        with open(base + ".hea", "wb") as f:
            f.write(upload.hea_bytes)
        with open(os.path.join(tmp, dat_name), "wb") as f:  # the name the header declares
            f.write(upload.dat_bytes)
        try:
            import wfdb

            rec = wfdb.rdrecord(base)  # same call as the original pipeline (channel 0 below)
            signal, fs = np.asarray(rec.p_signal[:, 0]), float(rec.fs)
            units = (rec.units[0] if rec.units else "") or "mV"
        except Exception:
            raise ECGValidationError("The .hea and .dat files could not be read as a WFDB recording.")
        if signal.size < WIN_SIZE:
            raise ECGValidationError("Signal is too short (needs at least 1500 samples).")
        if not np.all(np.isfinite(signal)):
            raise ECGValidationError("The signal contains invalid (NaN/Inf) samples.")
        return ParsedECG(signal=np.asarray(signal, dtype=float), fs=fs, units=units)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
