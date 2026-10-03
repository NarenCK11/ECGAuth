import { Link } from "react-router-dom";
import { ArrowRight, FileText, HeartPulse, ShieldCheck, UserCircle } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useFetch } from "../lib/hooks";
import { fmtDate, fmtDateTime } from "../lib/format";
import type { AttemptSummary, Profile, RecordList } from "../lib/types";
import { ErrorBanner, Loading, PageHead, ResultBadge } from "../components/ui";

export default function Dashboard() {
  const { user } = useAuth();
  const records = useFetch(() => api.get<RecordList>("/api/medical-records"), []);
  const history = useFetch(() => api.get<AttemptSummary[]>("/api/ecg/history"), []);
  const profile = useFetch(() => api.get<Profile>("/api/users/me"), []);
  if (!user) return null;

  const first = user.full_name.split(" ")[0];
  const latest = records.data?.items.slice(0, 3) ?? [];
  const recent = history.data?.slice(0, 4) ?? [];

  const tiles = [
    { to: "/medical-records", icon: <FileText size={20} />, title: "Medical Records", sub: `${records.data?.items.length ?? "-"} records` },
    { to: "/medical-records?tab=reports", icon: <FileText size={20} />, title: "Reports", sub: `${records.data?.items.filter((r) => r.report_title).length ?? "-"} reports` },
    { to: "/ecg-history", icon: <HeartPulse size={20} />, title: "ECG History", sub: `${profile.data?.authentication_count ?? "-"} verified sign-ins` },
    { to: "/profile", icon: <UserCircle size={20} />, title: "Profile", sub: user.email },
  ];

  return (
    <>
      <PageHead title={`Welcome, ${first}`} subtitle="ECGAuth Medical Portal" />
      <div className="grid cols-3">
        <div className="card stat"><div className="stat-label">Patient ID</div><div className="stat-value">{user.patient_id}</div><div className="stat-sub mono">{user.id}</div></div>
        <div className="card stat"><div className="stat-label">Authentication</div>
          <div className="stat-value" style={{ color: "var(--good-text)", display: "flex", alignItems: "center", gap: 8 }}><ShieldCheck size={26} />Verified</div>
          <div className="stat-sub">Signed in with enrolled ECG</div></div>
        <div className="card stat"><div className="stat-label">Last verified sign-in</div>
          <div className="stat-value" style={{ fontSize: 20, marginTop: 8 }}>{profile.data?.last_authenticated_at ? fmtDateTime(profile.data.last_authenticated_at) : "-"}</div>
          <div className="stat-sub">{profile.data?.enrollment ? `Enrollment ${profile.data.enrollment.reference}` : ""}</div></div>
      </div>

      <div className="grid cols-4">
        {tiles.map((t) => (
          <Link key={t.title} to={t.to} className="card card-pad" style={{ color: "inherit", textDecoration: "none" }}>
            <span className="brand-mark" style={{ marginBottom: 12 }}>{t.icon}</span>
            <h3>{t.title}</h3><p className="small muted" style={{ overflowWrap: "anywhere" }}>{t.sub}</p>
          </Link>
        ))}
      </div>

      <div className="grid cols-2" style={{ alignItems: "start" }}>
        <section className="card">
          <div className="card-head"><h2>Recent records</h2><Link to="/medical-records" className="small">View all <ArrowRight size={13} style={{ verticalAlign: -2 }} /></Link></div>
          {records.loading ? <Loading /> : records.error ? <div className="card-pad"><ErrorBanner message={records.error} /></div> :
            latest.length === 0 ? <div className="empty">No records yet</div> :
              latest.map((r) => (
                <div className="record" key={r.id} style={{ gridTemplateColumns: "92px 1fr" }}>
                  <div><div className="r-date">{fmtDate(r.record_date)}</div></div>
                  <div><div style={{ fontWeight: 600 }}>{r.record_type}</div><div className="r-dept">{r.department} · {r.doctor}</div></div>
                </div>
              ))}
        </section>
        <section className="card">
          <div className="card-head"><h2>Recent ECG authentications</h2><Link to="/ecg-history" className="small">View all <ArrowRight size={13} style={{ verticalAlign: -2 }} /></Link></div>
          {history.loading ? <Loading /> : recent.length === 0 ? <div className="empty">No authentication events</div> : (
            <div className="table-wrap"><table className="table"><tbody>
              {recent.map((a) => (
                <tr key={a.id}><td className="nowrap">{fmtDateTime(a.created_at)}</td><td><ResultBadge result={a.result} /></td>
                  <td className="num muted nowrap">{a.processing_time_ms ?? "-"} ms</td></tr>
              ))}
            </tbody></table></div>
          )}
        </section>
      </div>
    </>
  );
}
