"""Signal reading and normalisation, identical to the original pipeline."""
import numpy as np

WIN_SIZE = 1500
STRIDE = 1500  # non-overlapping, matches the original pipeline


def read_wfdb_signal(base_path: str) -> tuple[np.ndarray, float]:
    """Read channel 0 of a WFDB record at *base_path* (no extension). Returns (signal, fs)."""
    import wfdb

    rec = wfdb.rdrecord(base_path)
    return np.asarray(rec.p_signal[:, 0]), float(rec.fs)


def select_window(signal: np.ndarray) -> np.ndarray:
    """First non-overlapping window (original behaviour)."""
    if signal.size < WIN_SIZE:
        raise ValueError("Signal is too short (needs at least 1500 samples).")
    return signal[:WIN_SIZE]


def zscore(signal_array: np.ndarray) -> np.ndarray:
    """z-score normalise exactly as the original `process_signal_window` did."""
    w = np.asarray(signal_array, dtype=np.float32)
    std = float(np.std(w)) or 1.0
    return (w - float(np.mean(w))) / std


def downsample(values: np.ndarray, max_points: int = 800) -> np.ndarray:
    """Index-based downsample used for waveform display (original behaviour)."""
    vis = np.asarray(values, dtype=float)
    if vis.size > max_points:
        idx = np.linspace(0, vis.size - 1, max_points).astype(int)
        vis = vis[idx]
    return vis
