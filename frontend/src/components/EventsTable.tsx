import { fmtDateTime, METHOD_LABEL, REASON_LABEL } from "../lib/format";
import type { AuthEvent } from "../lib/types";
import { ResultBadge } from "./ui";

export default function EventsTable({ rows, showUser = true }: { rows: AuthEvent[]; showUser?: boolean }) {
  if (rows.length === 0) return <div className="empty">No authentication events.</div>;
  return (
    <div className="table-wrap">
      <table className="table">
        <thead><tr><th>Timestamp</th>{showUser && <th>User</th>}<th>Result</th><th>Method</th><th>Analysis version</th><th className="num">Processing</th></tr></thead>
        <tbody>
          {rows.map((e) => (
            <tr key={e.id}>
              <td className="nowrap">{fmtDateTime(e.created_at)}</td>
              {showUser && (
                <td>
                  <div style={{ fontWeight: 560 }}>{e.full_name ?? e.username ?? "-"}</div>
                  <div className="small muted">{e.patient_id ? `${e.patient_id} · ` : ""}{e.username ?? ""}{!e.user_id && e.username ? " (no account)" : ""}</div>
                </td>
              )}
              <td>
                <ResultBadge result={e.result} />
                {e.failure_reason && <div className="small muted" style={{ marginTop: 2 }}>{REASON_LABEL[e.failure_reason] ?? e.failure_reason}</div>}
              </td>
              <td>{METHOD_LABEL[e.method] ?? e.method}</td>
              <td className="mono">{e.pipeline_version ?? "-"}</td>
              <td className="num">{e.processing_time_ms !== null ? `${e.processing_time_ms} ms` : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
