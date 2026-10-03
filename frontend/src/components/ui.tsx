import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, FileCheck2, FileUp, Info, Moon, Sun, XCircle, Activity } from "lucide-react";

export function Brand({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="brand" aria-label="ECGAuth home">
      <span className="brand-mark"><Activity size={18} strokeWidth={2.6} /></span>
      ECGAuth
    </Link>
  );
}

export function ThemeToggle() {
  const [dark, setDark] = useState(() => {
    const t = document.documentElement.getAttribute("data-theme");
    return t ? t === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  });
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    try { localStorage.setItem("theme", dark ? "dark" : "light"); } catch { /* storage unavailable */ }
  }, [dark]);
  return (
    <button className="icon-btn" type="button" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} onClick={() => setDark((d) => !d)}>
      {dark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}

export function Spinner() { return <span className="spinner" role="status" aria-label="Loading" />; }

export function Loading({ label = "Loading" }: { label?: string }) {
  return <div className="row" style={{ padding: 28, justifyContent: "center", color: "var(--muted)" }}><Spinner />{label}…</div>;
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="banner error" role="alert"><XCircle size={16} /><span>{message}</span></div>;
}

export function InfoNote({ children }: { children: ReactNode }) {
  return <div className="banner info"><Info size={16} /><span>{children}</span></div>;
}

/** Result badge: colour is never the only signal (icon + label). */
export function ResultBadge({ result }: { result: string }) {
  const ok = result === "success";
  return <span className={`badge ${ok ? "good" : "bad"}`}>{ok ? <CheckCircle2 size={13} /> : <XCircle size={13} />}{ok ? "Success" : "Failed"}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const cls = status === "active" ? "good" : status === "inactive" ? "bad" : "warn";
  const label = status === "active" ? "Active" : status === "inactive" ? "Inactive" : "Pending";
  return <span className={`badge ${cls}`}>{label}</span>;
}

export function StatCard({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="card stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value num">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function PageHead({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>
      {actions && <div className="row wrap">{actions}</div>}
    </div>
  );
}

export function Pager({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  return (
    <div className="pager">
      <span>{from}-{Math.min(total, page * pageSize)} of {total.toLocaleString("en-GB")}</span>
      <div className="row">
        <button className="btn sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
        <span className="num">Page {page} / {pages}</span>
        <button className="btn sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}

/** A file picker styled as a drop zone; also accepts drag & drop. */
export function FileDrop({ label, accept, hint, file, onFile, name }: {
  label: string; accept: string; hint: string; file: File | null; onFile: (f: File | null) => void; name: string;
}) {
  const [over, setOver] = useState(false);
  return (
    <label className={`dropzone${over ? " over" : ""}${file ? " filled" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) onFile(f); }}>
      <span className="dz-icon">{file ? <FileCheck2 size={20} /> : <FileUp size={20} />}</span>
      <span className="grow">
        <span className="dz-title">{label}</span><br />
        <span className="hint">{file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB` : hint}</span>
      </span>
      <input type="file" name={name} accept={accept} onChange={(e) => onFile(e.target.files?.[0] ?? null)} aria-label={label} />
    </label>
  );
}

export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => { const h = setTimeout(() => setV(value), ms); return () => clearTimeout(h); }, [value, ms]);
  return v;
}
