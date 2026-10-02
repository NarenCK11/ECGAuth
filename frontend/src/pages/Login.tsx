import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Fingerprint, LockKeyhole } from "lucide-react";
import { ApiError, loginWithEcg } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ErrorBanner, FileDrop, Spinner } from "../components/ui";

export default function Login() {
  const nav = useNavigate();
  const { setLastLogin } = useAuth();
  const prefill = (useLocation().state as { username?: string; enrolled?: boolean } | null) ?? {};
  const [username, setUsername] = useState(prefill.username ?? "");
  const [hea, setHea] = useState<File | null>(null);
  const [dat, setDat] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!username.trim()) return setError("Enter your username or Patient ID.");
    if (!hea || !dat) return setError("Upload both your .hea and .dat ECG files.");
    setBusy(true);
    try {
      const result = await loginWithEcg(username.trim(), hea, dat);
      setLastLogin(result);          // analysis to display; the server's session cookie is the real identity
      nav("/ecg-analysis");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      setBusy(false);
    }
  }

  return (
    <form className="card auth-card" onSubmit={submit} noValidate>
      <div className="row" style={{ marginBottom: 6 }}><span className="brand-mark"><Fingerprint size={18} /></span><span className="muted small">Secure Patient Authentication</span></div>
      <h1>Sign in with your ECG</h1>
      <p className="secondary" style={{ margin: "6px 0 20px" }}>Your ECG is analyzed securely before access is granted.</p>
      {prefill.enrolled && <div className="banner info" style={{ marginBottom: 16 }}><span>Enrollment complete. Sign in with the same recording you enrolled.</span></div>}

      <div className="stack">
        <div className="field">
          <label htmlFor="username">Patient ID / Username</label>
          <input id="username" className="input" value={username} onChange={(e) => setUsername(e.target.value)}
            placeholder="PT-1001 or your username" autoComplete="username" autoCapitalize="none" spellCheck={false} />
        </div>
        <div className="field">
          <span className="label">ECG recording</span>
          <div className="stack" style={{ gap: 10 }}>
            <FileDrop name="hea_file" label="Header file (.hea)" accept=".hea" hint="Choose or drop your .hea file" file={hea} onFile={setHea} />
            <FileDrop name="dat_file" label="Signal file (.dat)" accept=".dat" hint="Choose or drop your .dat file" file={dat} onFile={setDat} />
          </div>
        </div>
        <ErrorBanner message={error} />
        <button className="btn primary lg" type="submit" disabled={busy}>{busy ? <><Spinner />Uploading…</> : "Authenticate"}</button>
      </div>

      <div className="auth-foot"><LockKeyhole size={15} style={{ flex: "none", marginTop: 2 }} /><span>
        New here? <Link to="/register">Create an account</Link>. Pre-trained model identities (for example Person_08) are analysed by the ECG model. Files are checked on the server and are not stored.</span></div>
    </form>
  );
}
