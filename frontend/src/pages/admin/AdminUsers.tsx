import { useState } from "react";
import { Search, UserCheck, UserX, X } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import { useFetch } from "../../lib/hooks";
import { fmtDate, fmtDateTime } from "../../lib/format";
import type { AdminUser, AdminUserDetail, Page } from "../../lib/types";
import EventsTable from "../../components/EventsTable";
import { ErrorBanner, Loading, PageHead, Pager, StatusBadge, useDebounced } from "../../components/ui";

const PAGE = 25;

function Drawer({ id, onClose, onChanged }: { id: string; onClose: () => void; onChanged: () => void }) {
  const { data, loading, error, reload } = useFetch(() => api.get<AdminUserDetail>(`/api/admin/users/${id}`), [id]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function toggle(u: AdminUser) {
    const next = u.status === "active" ? "inactive" : "active";
    if (next === "inactive" && !window.confirm(`Deactivate ${u.full_name}? They will be signed out and unable to sign in.`)) return;
    setBusy(true); setErr(null);
    try { await api.patch(`/api/admin/users/${u.id}/status`, { status: next }); reload(); onChanged(); }
    catch (e) { setErr(e instanceof ApiError ? e.message : "Update failed."); }
    finally { setBusy(false); }
  }

  const u = data?.user;
  return (
    <div className="drawer-back" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal aria-label="User details">
        <div className="row spread"><h2>{u?.full_name ?? "User"}</h2><button className="icon-btn" onClick={onClose} aria-label="Close"><X size={18} /></button></div>
        {loading ? <Loading /> : error || !u ? <ErrorBanner message={error ?? "Not found"} /> : (
          <>
            <section className="card card-pad">
              <dl className="kv">
                <dt>Patient ID</dt><dd><strong>{u.patient_id}</strong></dd>
                <dt>UUID</dt><dd className="mono">{u.id}</dd>
                <dt>Username</dt><dd>{u.username}</dd>
                <dt>Email</dt><dd>{u.email}</dd>
                <dt>Date of birth</dt><dd>{fmtDate(u.date_of_birth)}</dd>
                <dt>Registered</dt><dd>{fmtDateTime(u.created_at)}</dd>
                <dt>Status</dt><dd><StatusBadge status={u.status} /></dd>
                <dt>ECG enrollment</dt><dd>{u.enrolled ? <span className="mono">{data.enrollment_reference}</span> : "Not enrolled"}</dd>
                <dt>Authentications</dt><dd>{u.auth_total} total, {u.auth_failed} failed</dd>
              </dl>
              <ErrorBanner message={err} />
              {u.status !== "pending" && (
                <div style={{ marginTop: 16 }}>
                  <button className={`btn ${u.status === "active" ? "danger" : "primary"}`} disabled={busy} onClick={() => toggle(u)}>
                    {u.status === "active" ? <><UserX size={16} />Deactivate account</> : <><UserCheck size={16} />Activate account</>}
                  </button>
                </div>
              )}
            </section>
            <section className="card">
              <div className="card-head"><h3>Authentication history</h3></div>
              <EventsTable rows={data.recent_events} showUser={false} />
            </section>
          </>
        )}
      </aside>
    </div>
  );
}

export default function AdminUsers() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  const q = useDebounced(search);
  const { data, loading, refetching, error, reload } = useFetch(
    () => api.get<Page<AdminUser>>("/api/admin/users", { search: q, status, page, page_size: PAGE }), [q, status, page]);

  return (
    <>
      <PageHead title="Users" subtitle="Registered patients, enrollment status and account control" />
      <div className="filters">
        <div className="field" style={{ minWidth: 260 }}><label htmlFor="us">Search</label>
          <div style={{ position: "relative" }}>
            <Search size={15} style={{ position: "absolute", left: 11, top: 13, color: "var(--muted)" }} />
            <input id="us" className="input" style={{ paddingLeft: 32 }} placeholder="Name, username, email, PT-1001 or UUID" value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </div></div>
        <div className="field"><label htmlFor="ust">Status</label>
          <select id="ust" className="input" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All</option><option value="active">Active</option><option value="inactive">Inactive</option><option value="pending">Pending</option>
          </select></div>
      </div>
      <section className={`card${refetching ? " refetching" : ""}`}>
        {loading ? <Loading /> : error || !data ? <div className="card-pad"><ErrorBanner message={error ?? "Could not load users."} /></div> : data.items.length === 0 ? <div className="empty">No users match.</div> : (
          <>
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Patient ID</th><th>Name</th><th>Status</th><th>ECG</th><th>Registered</th><th>Last sign-in</th><th className="num">Failed / total</th></tr></thead>
              <tbody>
                {data.items.map((u) => (
                  <tr key={u.id} className="clickable" tabIndex={0} onClick={() => setOpen(u.id)} onKeyDown={(e) => e.key === "Enter" && setOpen(u.id)}>
                    <td><strong>{u.patient_id}</strong></td>
                    <td><div style={{ fontWeight: 560 }}>{u.full_name}</div><div className="small muted">{u.username}</div></td>
                    <td><StatusBadge status={u.status} /></td>
                    <td>{u.enrolled ? "Enrolled" : <span className="muted">Not enrolled</span>}</td>
                    <td className="nowrap">{fmtDate(u.created_at)}</td>
                    <td className="nowrap">{u.last_auth_at ? fmtDateTime(u.last_auth_at) : <span className="muted">-</span>}</td>
                    <td className="num">{u.auth_failed} / {u.auth_total}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
            <Pager page={page} pageSize={PAGE} total={data.total} onPage={setPage} />
          </>
        )}
      </section>
      {open && <Drawer id={open} onClose={() => setOpen(null)} onChanged={reload} />}
    </>
  );
}
