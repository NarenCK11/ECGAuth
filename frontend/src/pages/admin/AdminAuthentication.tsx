import { useState } from "react";
import { api } from "../../lib/api";
import { useFetch } from "../../lib/hooks";
import type { AuthEvent, Page } from "../../lib/types";
import EventsTable from "../../components/EventsTable";
import { ErrorBanner, Loading, PageHead, Pager, useDebounced } from "../../components/ui";

const PAGE = 25;

export default function AdminAuthentication() {
  const [user, setUser] = useState("");
  const [result, setResult] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const u = useDebounced(user);
  const { data, loading, refetching, error } = useFetch(
    () => api.get<Page<AuthEvent>>("/api/admin/authentication-events", { user: u, result, date_from: from, date_to: to, page, page_size: PAGE }),
    [u, result, from, to, page]);
  const reset = (fn: (v: string) => void) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => { fn(e.target.value); setPage(1); };

  return (
    <>
      <PageHead title="Authentication Events" subtitle="Every ECG sign-in attempt, including failures against unknown usernames" />
      <div className="filters">
        <div className="field" style={{ minWidth: 220 }}><label htmlFor="f-user">User</label>
          <input id="f-user" className="input" placeholder="Username, name or PT-1001" value={user} onChange={reset(setUser)} /></div>
        <div className="field"><label htmlFor="f-res">Result</label>
          <select id="f-res" className="input" value={result} onChange={reset(setResult)}><option value="">All</option><option value="success">Success</option><option value="failure">Failure</option></select></div>
        <div className="field"><label htmlFor="f-from">From</label><input id="f-from" type="date" className="input" value={from} onChange={reset(setFrom)} /></div>
        <div className="field"><label htmlFor="f-to">To</label><input id="f-to" type="date" className="input" value={to} onChange={reset(setTo)} /></div>
        {(user || result || from || to) && <button className="btn" onClick={() => { setUser(""); setResult(""); setFrom(""); setTo(""); setPage(1); }}>Clear filters</button>}
      </div>
      <section className={`card${refetching ? " refetching" : ""}`}>
        {loading ? <Loading /> : error || !data ? <div className="card-pad"><ErrorBanner message={error ?? "Could not load events."} /></div> : (
          <><EventsTable rows={data.items} /><Pager page={page} pageSize={PAGE} total={data.total} onPage={setPage} /></>
        )}
      </section>
    </>
  );
}
