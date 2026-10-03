import { Link } from "react-router-dom";
import { ArrowRight, FileHeart, Fingerprint, LineChart, LockKeyhole, ShieldCheck } from "lucide-react";

const BEAT = "M0,60 L40,60 L52,60 L60,46 L68,60 L84,60 L92,66 L100,10 L108,96 L116,60 L132,60 L150,60 L166,38 L184,60 L220,60";

export default function Landing() {
  return (
    <div className="stack" style={{ alignItems: "center", gap: 36, width: "100%" }}>
      <section className="hero">
        <div>
          <span className="badge info"><ShieldCheck size={13} />Biometric patient authentication</span>
          <h1 style={{ marginTop: 14 }}>Your heartbeat is your key.</h1>
          <p className="lead">ECGAuth verifies patients with their enrolled electrocardiogram, then opens a secure medical portal. No passwords to remember, nothing to guess.</p>
          <div className="row wrap">
            <Link to="/login" className="btn primary lg">Sign in with ECG<ArrowRight size={18} /></Link>
            <Link to="/register" className="btn lg">Create account</Link>
          </div>
        </div>
        <div className="card hero-art" aria-hidden>
          <svg viewBox="0 0 220 110" style={{ width: "100%", display: "block" }}>
            {[20, 40, 60, 80, 100].map((y) => <line key={y} x1="0" x2="220" y1={y} y2={y} stroke="var(--grid)" />)}
            {[0, 44, 88, 132, 176, 220].map((x) => <line key={x} y1="0" y2="110" x1={x} x2={x} stroke="var(--grid)" />)}
            <path d={BEAT} fill="none" stroke="var(--series-1)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" pathLength={1}
              style={{ strokeDasharray: 1, strokeDashoffset: 1, animation: "draw 2.6s ease-out forwards" }} />
          </svg>
          <style>{`@keyframes draw { to { stroke-dashoffset: 0; } } @media (prefers-reduced-motion: reduce) { path { animation: none !important; stroke-dashoffset: 0 !important; } }`}</style>
          <div className="row spread" style={{ marginTop: 8 }}>
            <span className="small muted">Lead II · 360 Hz</span>
            <span className="badge good"><ShieldCheck size={13} />Identity verified</span>
          </div>
        </div>
      </section>

      <section className="features" aria-label="How it works">
        <div className="card feature"><span className="dz-icon"><FileHeart size={20} /></span><h3>1 · Enroll your ECG</h3>
          <p className="secondary small" style={{ marginTop: 6 }}>Register once and upload a WFDB recording (.hea + .dat). It becomes your credential; only its cryptographic fingerprint is stored.</p></div>
        <div className="card feature"><span className="dz-icon"><Fingerprint size={20} /></span><h3>2 · Authenticate</h3>
          <p className="secondary small" style={{ marginTop: 6 }}>Upload your recording at sign-in. The server compares it with your enrollment and decides. The browser never does.</p></div>
        <div className="card feature"><span className="dz-icon"><LineChart size={20} /></span><h3>3 · See the analysis</h3>
          <p className="secondary small" style={{ marginTop: 6 }}>Watch your signal move through the pipeline, then enter the medical portal with a short-lived, secure session.</p></div>
      </section>

      <p className="small muted row" style={{ gap: 6 }}><LockKeyhole size={14} />Sessions use HttpOnly cookies. Uploaded recordings are never stored or exposed through URLs.</p>
    </div>
  );
}
