import os
import json
import uuid
import logging
from datetime import datetime

import numpy as np
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename

# third-party stack used by your original pipeline
import joblib
import onnxruntime as ort
import wfdb

from flask_cors import CORS
# -----------------------------
# App & config
# -----------------------------
logging.basicConfig(level=logging.INFO)
app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)
app.secret_key = os.environ.get('ECG_AUTH_SECRET', 'replace-with-secure-secret')

UPLOAD_ROOT = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_ROOT, exist_ok=True)

# Model / data constants
WIN_SIZE   = 1500
STRIDE     = 1500            # non-overlapping, matches your earlier pipeline
THRESHOLD  = 0.70            # similarity threshold (for claimed user prob)

# -----------------------------
# Load models & mapping
# -----------------------------
def _load_model_assets():
    base = os.path.dirname(__file__)
    app.logger.info("Loading models & mapping...")
    ort_sess = ort.InferenceSession(
        os.path.join(base, "feature_model.onnx"),
        providers=['CPUExecutionProvider']
    )
    rp       = joblib.load(os.path.join(base, "rp_transformer_all.joblib"))
    scaler   = joblib.load(os.path.join(base, "scaler_all.joblib"))
    svm      = joblib.load(os.path.join(base, "svm_classifier_all.joblib"))
    with open(os.path.join(base, "user_mapping.json"), "r") as f:
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

    app.logger.info("Models loaded successfully.")
    return ort_sess, rp, scaler, svm, name2label, label2name, name2label_ci

try:
    ORT_SESSION, RP, SCALER, SVM_MODEL, NAME_TO_LABEL, LABEL_TO_NAME, NAME_TO_LABEL_CI = _load_model_assets()
except Exception as e:
    app.logger.error("FATAL: could not load model assets: %s", e)
    raise

# -----------------------------
# Helpers
# -----------------------------
@app.context_processor
def inject_year():
    return {'year': datetime.now().year}

def process_signal_window(signal_array: np.ndarray) -> np.ndarray:
    """
    z-score normalize -> ONNX (128D) -> RP (96D) -> Scaler
    Returns shape (1, 96)
    """
    w = np.asarray(signal_array, dtype=np.float32)
    std = float(np.std(w)) or 1.0
    w_norm = (w - float(np.mean(w))) / std
    onnx_in = w_norm.reshape(1, WIN_SIZE, 1).astype(np.float32)

    in_name  = ORT_SESSION.get_inputs()[0].name
    out_name = ORT_SESSION.get_outputs()[0].name
    feat128  = ORT_SESSION.run([out_name], {in_name: onnx_in})[0]   # (1, 128)

    feat96   = RP.transform(feat128)         # (1, 96)
    feat96s  = SCALER.transform(feat96)      # (1, 96)
    return feat96s

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
    """
    Return index of claimed_label inside classes; handles type differences.
    """
    try:
        # direct equality (works for ints)
        if claimed_label in classes:
            return int(np.where(classes == claimed_label)[0][0])
        # else string compare
        classes_str = np.array(list(map(str, classes)))
        hit = np.where(classes_str == str(claimed_label))[0]
        if hit.size > 0:
            return int(hit[0])
    except Exception:
        pass
    return None

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/demo")
def demo():
    return render_template("demo.html")

@app.route("/how_it_works")
def how_it_works():
    return render_template("how_it_works.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# -----------------------------
# Identify (username + .hea/.dat only)
# -----------------------------
@app.route("/identify", methods=["POST"])
def identify():
    hea_file = request.files.get("hea_file")
    dat_file = request.files.get("dat_file")
    username_claim = (request.form.get("username") or "").strip()

    if not username_claim:
        return jsonify({"error": "Please enter your username."}), 400
    if not hea_file or not dat_file:
        return jsonify({"error": "Please provide both header (.hea) and signal (.dat) files."}), 400

    # Map username -> label (case-insensitive)
    claimed_label = None
    if username_claim in NAME_TO_LABEL:
        claimed_label = NAME_TO_LABEL[username_claim]
    else:
        claimed_label = NAME_TO_LABEL_CI.get(username_claim.lower())

    # Save pair into a unique subfolder so wfdb can read by base
    subdir = os.path.join(UPLOAD_ROOT, f"rec_{uuid.uuid4().hex[:8]}")
    os.makedirs(subdir, exist_ok=True)

    # Use the .hea base name for both files (ensures a proper pair)
    base = os.path.splitext(secure_filename(hea_file.filename))[0]
    base_path = os.path.join(subdir, base)
    hea_path = base_path + ".hea"
    dat_path = base_path + ".dat"
    hea_file.save(hea_path)
    dat_file.save(dat_path)

    try:
        # Read ECG, channel 0
        rec = wfdb.rdrecord(base_path)
        sig = np.asarray(rec.p_signal[:, 0])

        if sig.size < WIN_SIZE:
            return jsonify({"error": "Signal is too short (needs at least 1500 samples)."}), 400

        # Use first non-overlapping window (your original behavior)
        window = sig[:WIN_SIZE]
        feat = process_signal_window(window)              # (1, 96)

        # Probabilities
        classes = getattr(SVM_MODEL, "classes_", None)
        if classes is None:
            return jsonify({"error": "Model classes_ missing"}), 500

        # Try calibrated probabilities
        probs = None
        if hasattr(SVM_MODEL, "predict_proba"):
            try:
                probs = SVM_MODEL.predict_proba(feat)[0]  # (n_classes,)
            except Exception:
                probs = None

        # Fallback: decision_function -> softmax
        if probs is None:
            # --- ADD THIS LINE ---
            app.logger.warning("!!! Using FALLBACK (decision_function + softmax) path !!!")
            # ---------------------
            margins = SVM_MODEL.decision_function(feat)
            margins = np.atleast_1d(margins)
            if margins.ndim == 1:
                # binary case: shape (n_classes,) should be 2; if 1, synthesize
                if margins.shape[0] == 1:
                    margins = np.hstack([-margins, margins])
            probs = softmax(margins)
            
            # --- FIX START ---
            # Ensure probs is 1D (shape (n_classes,)) to match predict_proba
            # This fixes "only length-1 arrays can be converted to Python scalars"
            if probs.ndim == 2:
                probs = probs[0]
            # --- FIX END ---

        # Top prediction (for display)
        top_idx = int(np.argmax(probs))
        top_label_raw = classes[top_idx]
        top_label = _to_int_or_same(top_label_raw)
        predicted_name = LABEL_TO_NAME.get(top_label, f"Person_{top_label}")

        # Claimed similarity (probability tied to username)
        claim_idx = None
        similarity = None
        if claimed_label is not None:
            claim_idx = _find_claim_idx(classes, claimed_label)
            if claim_idx is not None:
                similarity = float(probs[claim_idx])

        # Auth rule: predicted == claimed OR similarity >= THRESHOLD
        authenticated = False
        if claimed_label is not None:
            try:
                authenticated = (int(claimed_label) == int(top_label))
            except Exception:
                authenticated = (str(claimed_label) == str(top_label))
            if not authenticated and similarity is not None:
                authenticated = (similarity >= THRESHOLD)
        # Auth rule: predicted == claimed AND similarity >= THRESHOLD
        # authenticated = False
        # if claimed_label is not None and similarity is not None:
        #     # --- CONDITION 1 ---
        #     is_top_prediction = False
        #     try:
        #         is_top_prediction = (int(claimed_label) == int(top_label))
        #     except Exception:
        #         is_top_prediction = (str(claimed_label) == str(top_label))
            
        #     # --- CONDITION 2 ---
        #     is_above_threshold = (similarity >= THRESHOLD)

        #     # --- COMBINED 'AND' LOGIC ---
        #     authenticated = (is_top_prediction and is_above_threshold)

        # Downsample waveform for canvas
        vis = window.astype(float)
        if vis.size > 800:
            idx = np.linspace(0, vis.size - 1, 800).astype(int)
            vis = vis[idx]

        # Cleanup files
        try:
            for p in [hea_path, dat_path]:
                if os.path.exists(p): os.remove(p)
            # remove empty subdir
            if os.path.isdir(subdir) and not os.listdir(subdir):
                os.rmdir(subdir)
        except Exception:
            pass

        return jsonify({
            "authenticated": bool(authenticated),
            "predicted_name": predicted_name,
            "predicted_label": top_label,
            "similarity": float(similarity) if similarity is not None else None,
            "threshold": THRESHOLD,
            "claimed_name": username_claim,
            "claimed_label": claimed_label,
            "claim_idx": claim_idx,
            "waveform": vis.tolist()
        })

    except Exception as e:
        app.logger.exception("Error in /identify")
        return jsonify({"error": str(e)}), 500
    finally:
        # best-effort cleanup if something remained
        try:
            for p in [hea_path, dat_path]:
                if p and os.path.exists(p): os.remove(p)
            if os.path.isdir(subdir) and not os.listdir(subdir):
                os.rmdir(subdir)
        except Exception:
            pass

# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    app.logger.info("ECGAuth backend started on http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)