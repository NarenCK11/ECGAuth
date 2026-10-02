import { useState } from "react";
import { X } from "lucide-react";
import { api } from "../lib/api";
import { useFetch } from "../lib/hooks";
import { fmtDate, fmtTime, METHOD_LABEL } from "../lib/format";
import type { AttemptDetail, AttemptSummary } from "../lib/types";
import AnalysisView from "../components/AnalysisView";
import { ErrorBanner, InfoNote, Loading, PageHead, ResultBadge } from "../components/ui";

function Detail({ id, onClose }: { id: string; onClose: () => void }) {
  const { data, loading, error } = useFetch(() => api.get<AttemptDetail>(`/api/ecg/${id}`), [id]);
  return (
    <div className="drawer-back" onClick={onClose}>
      <aside className="drawer" style={{ width: "min(1100px, 100%)" }} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal aria-label="Authentication event">
        <div className="row spread">
          <h2>Authentication event</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>
        {loading ? <Loading /> : error ? <ErrorBanner message={error} /> : data && (
          <>
            <dl className="kv">
              <dt>Date</dt><dd>{fmtDate(data.created_at)} at {fmtTime(data.created_at)}</dd>
              <dt>Result</dt><dd><ResultBadge result={data.result} /></dd>
              <dt>Method</dt><dd>{METHOD_LABEL[data.method] ?? data.method}</dd>
              <dt>Enrollment</dt><dd className="mono">{data.enrollment_reference ?? "-"}</dd>
            </dl>
            {data.analysis ? <AnalysisView analysis={data.analysis} animate={false} /> : <InfoNote>{data.note ?? "No analysis is available for this event."}</InfoNote>}
          </>
        )}
      </aside>
    </div>
  );
}

export default function EcgHistory() {
  const { data, loading, error } = useFetch(() => api.get<AttemptSummary[]>("/api/ecg/history"), []);
  const [open, setOpen] = useState<string | null>(null);
  return (
    <>
      <PageHead title="ECG Authentication History" subtitle="Every sign-in attempt on your account. Select an event to see its analysis." />
      <section className="card">
        {loading ? <Loading /> : error ? <div className="card-pad"><ErrorBanner message={error} /></div> :
          !data || data.length === 0 ? <div className="empty">No authentication events yet.</div> : (
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Date</th><th>Time</th><th>Result</th><th className="num">Duration</th><th>Analysis version</th><th>ECG enrollment</th></tr></thead>
                <tbody>
                  {data.map((a) => (
                    <tr key={a.id} className="clickable" tabIndex={0} onClick={() => setOpen(a.id)} onKeyDown={(e) => e.key === "Enter" && setOpen(a.id)}>
                      <td className="nowrap">{fmtDate(a.created_at)}</td><td className="nowrap num">{fmtTime(a.created_at)}</td>
                      <td><ResultBadge result={a.result} /></td>
                      <td className="num">{a.processing_time_ms ?? "-"} ms</td>
                      <td className="mono">{a.pipeline_version ?? "-"}</td><td className="mono">{a.enrollment_reference ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </section>
      {open && <Detail id={open} onClose={() => setOpen(null)} />}
    </>
  );
}
