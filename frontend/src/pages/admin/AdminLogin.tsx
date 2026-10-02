import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import { useAdmin } from "../../lib/auth";
import { ErrorBanner, Spinner } from "../../components/ui";

export default function AdminLogin() {
  const { admin, refresh } = useAdmin();
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (admin) return <Navigate to="/admin/dashboard" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.post("/api/admin/login", { username, password });
      await refresh();
      nav("/admin/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed. Please try again.");
      setBusy(false);
    }
  }

  return (
    <form className="card auth-card" onSubmit={submit}>
      <div className="row" style={{ marginBottom: 6 }}><span className="brand-mark"><ShieldCheck size={18} /></span><span className="muted small">Restricted area</span></div>
      <h1>ECGAuth Administration</h1>
      <p className="secondary" style={{ margin: "6px 0 20px" }}>Administrators sign in with a password. Patients use the ECG sign-in.</p>
      <div className="stack">
        <div className="field"><label htmlFor="au">Username</label><input id="au" className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoCapitalize="none" required /></div>
        <div className="field"><label htmlFor="ap">Password</label><input id="ap" type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required /></div>
        <ErrorBanner message={error} />
        <button className="btn primary lg" type="submit" disabled={busy || !username || !password}>{busy ? <><Spinner />Signing in…</> : "Sign In"}</button>
      </div>
    </form>
  );
}
