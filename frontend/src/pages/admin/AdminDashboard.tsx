import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2, Cpu } from "lucide-react";
import { api } from "../../lib/api";
import { useFetch } from "../../lib/hooks";
import { ACTION_LABEL, fmtDate, fmtDateTime, fmtNumber, shortDay } from "../../lib/format";
import type { Dashboard } from "../../lib/types";
import ColumnChart from "../../components/ColumnChart";
import EventsTable from "../../components/EventsTable";
import { ErrorBanner, Loading, PageHead, StatCard, StatusBadge } from "../../components/ui";

export const SERIES = [
  { name: "Successful", color: "var(--series-1)" },
  { name: "Failed", color: "var(--series-2)" },
];

export default function AdminDashboard() {
  const { data, loading, refetching, error } = useFetch(() => api.get<Dashboard>("/api/admin/dashboard"), []);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBanner message={error ?? "Could not load the dashboard."} />;
  const t = data.totals;
  const rate = t.authentication_events ? Math.round((t.successful / t.authentication_events) * 100) : null;

  return (
    <div className={refetching ? "refetching" : undefined} style={{ display: "contents" }}>
      <PageHead title="ECGAuth Administration" subtitle="Overview of registrations and authentication activity" />
      <div className="grid cols-4">
        <StatCard label="Registered users" value={fmtNumber(t.registered_users)} sub={t.pending_users ? `${t.pending_users} awaiting ECG enrollment` : "All enrolled"} />
        <StatCard label="Authentication events" value={fmtNumber(t.authentication_events)} sub={`${fmtNumber(t.active_users_7d)} active users (7 days)`} />
        <StatCard label="Successful" value={fmtNumber(t.successful)} sub={rate !== null ? `${rate}% success rate` : undefined} />
        <StatCard label="Failed" value={fmtNumber(t.failed)} sub={`${fmtNumber(t.failed_24h)} in the last 24 h`} />
      </div>

      <div className="grid split" style={{ alignItems: "start" }}>
        <section className="card">
          <div className="card-head"><div><h2>Authentication activity</h2><p className="small muted">Attempts per day, last 14 days (UTC)</p></div></div>
          <div className="card-pad">
            <ColumnChart title="Day" series={SERIES} labelEvery={2}
              data={data.trend.map((d) => ({ label: shortDay(d.date), tip: fmtDate(d.date), values: [d.success, d.failure] }))} />
          </div>
        </section>
        <section className="card">
          <div className="card-head"><h2>Recent registrations</h2><Link to="/admin/users" className="small">All users <ArrowRight size={13} style={{ verticalAlign: -2 }} /></Link></div>
          {data.recent_registrations.length === 0 ? <div className="empty">No registrations yet.</div> : (
            <div className="table-wrap"><table className="table"><tbody>
              {data.recent_registrations.map((u) => (
                <tr key={u.id}><td><div style={{ fontWeight: 560 }}>{u.full_name}</div><div className="small muted">{u.patient_id} · {fmtDate(u.created_at)}</div></td><td><StatusBadge status={u.status} /></td></tr>
              ))}
            </tbody></table></div>
          )}
        </section>
      </div>

      <section className="card">
        <div className="card-head"><h2>Recent authentication events</h2><Link to="/admin/authentication" className="small">All events <ArrowRight size={13} style={{ verticalAlign: -2 }} /></Link></div>
        <EventsTable rows={data.recent_events} />
      </section>

      <section className="card">
        <div className="card-head"><h2>System activity</h2>
          <div className="row wrap">
            <span className={`badge ${data.system.ml_available ? "good" : "bad"}`}><Cpu size={13} />ML model {data.system.ml_available ? "online" : "unavailable"}</span>
            <span className="badge neutral mono">{data.system.pipeline_version}</span>
          </div>
        </div>
        <div className="table-wrap"><table className="table"><tbody>
          {data.system.recent_activity.map((a) => (
            <tr key={a.id}><td className="nowrap">{fmtDateTime(a.created_at)}</td>
              <td><CheckCircle2 size={13} style={{ verticalAlign: -2, color: "var(--muted)" }} /> {ACTION_LABEL[a.action] ?? a.action}</td>
              <td className="muted">{a.actor_name ?? a.actor_role}</td></tr>
          ))}
        </tbody></table></div>
      </section>
    </div>
  );
}
