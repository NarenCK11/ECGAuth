import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { CheckCircle2, Copy } from "lucide-react";
import { api, ApiError } from "../lib/api";
import type { User } from "../lib/types";
import { ErrorBanner, FileDrop, Spinner } from "../components/ui";
import { Steps } from "./Register";

interface Enrolled { user: User; enrollment_reference: string; message: string }

export default function Enroll() {
  const nav = useNavigate();
  const registered = (useLocation().state as { user?: User } | null)?.user;
  const [hea, setHea] = useState<File | null>(null);
  const [dat, setDat] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [done, setDone] = useState<Enrolled | null>(null);
  const [copied, setCopied] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!hea || !dat) return setError("Upload both your .hea and .dat ECG files.");
    setBusy(true);
    try {
      const form = new FormData();
      form.set("hea_file", hea);
      form.set("dat_file", dat);
      setDone(await api.postForm<Enrolled>("/api/auth/enroll", form));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setExpired(true);
      setError(err instanceof ApiError ? err.message : "Enrollment failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="card auth-card wide reveal">
        <Steps current={3} />
        <div className="row" style={{ gap: 14, marginBottom: 16 }}>
          <span className="v-icon" style={{ display: "grid", placeItems: "center", width: 48, height: 48, borderRadius: "50%", background: "var(--good)", color: "#fff" }}><CheckCircle2 size={26} /></span>
          <div><h1>Account created</h1><p className="secondary">{done.message}</p></div>
        </div>
        <dl className="kv" style={{ margin: "8px 0 20px" }}>
          <dt>Name</dt><dd>{done.user.full_name}</dd>
          <dt>Patient ID</dt><dd><strong>{done.user.patient_id}</strong></dd>
          <dt>Username</dt><dd>{done.user.username}</dd>
          <dt>Account UUID</dt>
          <dd className="row" style={{ gap: 8 }}><span className="mono">{done.user.id}</span>
            <button type="button" className="icon-btn" aria-label="Copy UUID" onClick={() => { void navigator.clipboard?.writeText(done.user.id); setCopied(true); }}><Copy size={15} /></button>
            {copied && <span className="hint">Copied</span>}</dd>
          <dt>Enrollment</dt><dd className="mono">{done.enrollment_reference}</dd>
        </dl>
        <div className="banner info" style={{ marginBottom: 16 }}><span>Keep your .hea and .dat files safe. They are your credential, and the exact files are required to sign in.</span></div>
        <button className="btn primary lg" style={{ width: "100%" }} onClick={() => nav("/login", { state: { username: done.user.username, enrolled: true } })}>Continue to sign in</button>
      </div>
    );
  }

  return (
    <form className="card auth-card wide" onSubmit={submit} noValidate>
      <Steps current={2} />
      <h1>Enroll your ECG</h1>
      <p className="secondary" style={{ margin: "6px 0 20px" }}>
        {registered ? <>Hi {registered.full_name.split(" ")[0]}, upload</> : <>Upload</>} the WFDB recording (.hea + .dat) you will use to sign in. The files are validated and fingerprinted (SHA-256); the files themselves are not kept.
      </p>
      <div className="stack">
        <FileDrop name="hea_file" label="Header file (.hea)" accept=".hea" hint="Choose or drop your .hea file" file={hea} onFile={setHea} />
        <FileDrop name="dat_file" label="Signal file (.dat)" accept=".dat" hint="Choose or drop your .dat file" file={dat} onFile={setDat} />
        <p className="hint">Requirements: a single-file WFDB recording of at least 1,500 samples, under 5 MB.</p>
        <ErrorBanner message={error} />
        {expired && <p className="small">Your registration session has expired. <Link to="/register">Register again</Link>.</p>}
        <button className="btn primary lg" type="submit" disabled={busy}>{busy ? <><Spinner />Validating and enrolling…</> : "Enroll ECG"}</button>
      </div>
    </form>
  );
}
