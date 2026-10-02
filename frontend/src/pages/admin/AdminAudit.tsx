import { useState } from "react";
import { api } from "../../lib/api";
import { useFetch } from "../../lib/hooks";
import { ACTION_LABEL, fmtDateTime } from "../../lib/format";
import type { AuditLog, Page } from "../../lib/types";
import { ErrorBanner, Loading, PageHead, Pager } from "../../components/ui";

const PAGE = 50;

function details(meta: Record<string, unknown> | null): string {
  if (!meta) return "";
  return Object.entries(meta).filter(([, v]) => v !== null && v !== undefined && v !== "").map(([k, v]) => `${k}: ${String(v)}`).join(" · ");
}

export default function AdminAudit() {
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const { data, loading, refetching, error } = useFetch(() => api.get<Page<AuditLog>>("/api/admin/audit-logs", { action, page, page_size: PAGE }), [action, page]);
  return (
    <>
      <PageHead title="Audit Logs" subtitle="Security-relevant events recorded by the server" />
      <div className="filters">
        <div className="field"><label htmlFor="aa">Action</label>
          <select id="aa" className="input" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }}>
            <option value="">All actions</option>
            {Object.entries(ACTION_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select></div>
      </div>
      <section className={`card${refetching ? " refetching" : ""}`}>
        {loading ? <Loading /> : error || !data ? <div className="card-pad"><ErrorBanner message={error ?? "Could not load audit logs."} /></div> : data.items.length === 0 ? <div className="empty">No audit events.</div> : (
          <>
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Timestamp</th><th>Actor</th><th>Action</th><th>Details</th></tr></thead>
              <tbody>{data.items.map((l) => (
                <tr key={l.id}>
                  <td className="nowrap">{fmtDateTime(l.created_at)}</td>
                  <td>{l.actor_name ?? <span className="muted">anonymous</span>}<div className="small muted">{l.actor_role}</div></td>
                  <td>{ACTION_LABEL[l.action] ?? l.action}</td>
                  <td className="small secondary" style={{ maxWidth: 420, overflowWrap: "anywhere" }}>{details(l.metadata)}</td>
                </tr>))}</tbody>
            </table></div>
            <Pager page={page} pageSize={PAGE} total={data.total} onPage={setPage} />
          </>
        )}
      </section>
    </>
  );
}
