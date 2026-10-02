import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import type { User } from "../lib/types";
import { ErrorBanner, Spinner } from "../components/ui";

export function Steps({ current }: { current: 1 | 2 | 3 }) {
  const items = ["Account", "ECG enrollment", "Done"];
  return (
    <div className="steps" aria-label={`Step ${current} of 3`}>
      {items.map((label, i) => {
        const n = i + 1;
        const cls = n < current ? "done" : n === current ? "on" : "";
        return (
          <span className="step-wrap" style={{ display: "contents" }} key={label}>
            <span className={`step ${cls}`}><span className="dot">{n < current ? "✓" : n}</span><span>{label}</span></span>
            {n < items.length && <span className="bar" />}
          </span>
        );
      })}
    </div>
  );
}

export default function Register() {
  const nav = useNavigate();
  const [f, setF] = useState({ full_name: "", email: "", date_of_birth: "", username: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF((s) => ({ ...s, [k]: e.target.value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (Object.values(f).some((v) => !v.trim())) return setError("Please complete every field.");
    setBusy(true);
    try {
      const res = await api.post<{ user: User }>("/api/auth/register", f);
      nav("/enroll", { state: { user: res.user } });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed. Please try again.");
      setBusy(false);
    }
  }

  return (
    <form className="card auth-card wide" onSubmit={submit} noValidate>
      <Steps current={1} />
      <h1>Create your account</h1>
      <p className="secondary" style={{ margin: "6px 0 20px" }}>Next you will enroll an ECG recording. That recording is how you will sign in.</p>
      <div className="stack">
        <div className="form-grid">
          <div className="field"><label htmlFor="name">Full name</label><input id="name" className="input" value={f.full_name} onChange={set("full_name")} autoComplete="name" /></div>
          <div className="field"><label htmlFor="dob">Date of birth</label><input id="dob" type="date" className="input" value={f.date_of_birth} onChange={set("date_of_birth")} autoComplete="bday" max={new Date().toISOString().slice(0, 10)} /></div>
          <div className="field"><label htmlFor="email">Email</label><input id="email" type="email" className="input" value={f.email} onChange={set("email")} autoComplete="email" /></div>
          <div className="field"><label htmlFor="user">Username</label><input id="user" className="input" value={f.username} onChange={set("username")} autoCapitalize="none" spellCheck={false} autoComplete="username" />
            <span className="hint">3-32 characters: letters, digits, . _ -</span></div>
        </div>
        <ErrorBanner message={error} />
        <button className="btn primary lg" type="submit" disabled={busy}>{busy ? <><Spinner />Creating…</> : "Continue to ECG enrollment"}</button>
      </div>
      <div className="auth-foot"><span>Already enrolled? <Link to="/login">Sign in</Link></span></div>
    </form>
  );
}
