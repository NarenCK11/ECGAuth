import { api } from "../../lib/api";
import { useFetch } from "../../lib/hooks";
import { fmtDate, METHOD_LABEL, REASON_LABEL, shortDay } from "../../lib/format";
import type { Analytics } from "../../lib/types";
import ColumnChart from "../../components/ColumnChart";
import { BarList } from "../../components/smallCharts";
import { ErrorBanner, Loading, PageHead, StatCard } from "../../components/ui";
import { SERIES } from "./AdminDashboard";

export default function AdminAnalytics() {
  const { data, loading, refetching, error } = useFetch(() => api.get<Analytics>("/api/admin/analytics"), []);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBanner message={error ?? "Could not load analytics."} />;
  const p = data.processing_ms;

  return (
    <div className={refetching ? "refetching" : undefined} style={{ display: "contents" }}>
      <PageHead title="Analytics" subtitle="Authentication trends over the last 30 days" />
      <div className="grid cols-3">
        <StatCard label="Average processing time" value={p.avg !== null ? `${p.avg} ms` : "-"} sub={`${p.samples} attempts measured`} />
        <StatCard label="Median (p50)" value={p.p50 !== null ? `${p.p50} ms` : "-"} />
        <StatCard label="95th percentile" value={p.p95 !== null ? `${p.p95} ms` : "-"} />
      </div>

      <section className="card">
        <div className="card-head"><div><h2>Authentication trend</h2><p className="small muted">Attempts per day, last 30 days (UTC)</p></div></div>
        <div className="card-pad">
          <ColumnChart title="Day" series={SERIES} labelEvery={3} height={240}
            data={data.daily.map((d) => ({ label: shortDay(d.date), tip: fmtDate(d.date), values: [d.success, d.failure] }))} />
        </div>
      </section>

      <div className="grid cols-2" style={{ alignItems: "start" }}>
        <section className="card">
          <div className="card-head"><div><h2>Activity by hour</h2><p className="small muted">All attempts, hour of day (UTC)</p></div></div>
          <div className="card-pad">
            <ColumnChart title="Hour" series={[{ name: "Attempts", color: "var(--series-1)" }]} labelEvery={3}
              data={data.hourly_utc.map((h) => ({ label: String(h.hour).padStart(2, "0"), tip: `${String(h.hour).padStart(2, "0")}:00-${String(h.hour).padStart(2, "0")}:59`, values: [h.count] }))} />
          </div>
        </section>
        <section className="card">
          <div className="card-head"><h2>Why attempts failed</h2></div>
          <div className="card-pad"><BarList empty="No failed attempts" rows={data.failure_reasons.map((r) => ({ label: REASON_LABEL[r.reason] ?? r.reason, value: r.count }))} /></div>
        </section>
        <section className="card">
          <div className="card-head"><h2>Most failed usernames</h2></div>
          <div className="card-pad"><BarList empty="No failed attempts" rows={data.top_failed_usernames.map((r) => ({ label: r.username ?? "(blank)", value: r.count }))} /></div>
        </section>
        <section className="card">
          <div className="card-head"><h2>Users and methods</h2></div>
          <div className="card-pad stack" style={{ gap: 22 }}>
            <div><div className="label" style={{ marginBottom: 8 }}>Account status</div>
              <BarList rows={data.user_status.map((r) => ({ label: r.status[0].toUpperCase() + r.status.slice(1), value: r.count }))} /></div>
            <div><div className="label" style={{ marginBottom: 8 }}>Authentication method (30 days)</div>
              <BarList empty="No attempts" rows={data.by_method.map((r) => ({ label: METHOD_LABEL[r.method] ?? r.method, value: r.count }))} /></div>
          </div>
        </section>
      </div>
    </div>
  );
}
