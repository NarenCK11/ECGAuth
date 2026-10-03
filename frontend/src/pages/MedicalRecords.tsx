import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ChevronDown, ChevronUp, FileText } from "lucide-react";
import { api } from "../lib/api";
import { useFetch } from "../lib/hooks";
import { fmtDate } from "../lib/format";
import type { MedicalRecord, RecordList } from "../lib/types";
import { ErrorBanner, Loading, PageHead } from "../components/ui";

function Record({ r }: { r: MedicalRecord }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="record">
      <div><div className="r-date">{fmtDate(r.record_date)}</div><div className="r-dept">{r.department}</div></div>
      <div className="grow">
        <div style={{ fontWeight: 620 }}>{r.record_type}</div>
        <div className="small secondary">{r.doctor}{r.diagnosis ? ` · ${r.diagnosis}` : ""}</div>
        {open && (
          <dl className="kv reveal" style={{ marginTop: 12 }}>
            <dt>Diagnosis</dt><dd>{r.diagnosis ?? "-"}</dd>
            <dt>Notes</dt><dd>{r.notes ?? "-"}</dd>
            {r.report_title && <><dt>Attached report</dt><dd><span className="badge info"><FileText size={13} />{r.report_title}</span><div className="small secondary" style={{ marginTop: 6 }}>{r.report_summary}</div></dd></>}
          </dl>
        )}
      </div>
      <button className="btn sm ghost" onClick={() => setOpen((o) => !o)} aria-expanded={open}>{open ? <>Hide<ChevronUp size={14} /></> : <>Details<ChevronDown size={14} /></>}</button>
    </div>
  );
}

export default function MedicalRecords() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "reports" ? "reports" : "all";
  const [dept, setDept] = useState("");
  const { data, loading, error } = useFetch(() => api.get<RecordList>("/api/medical-records"), []);

  const departments = useMemo(() => Array.from(new Set(data?.items.map((r) => r.department) ?? [])).sort(), [data]);
  const rows = (data?.items ?? []).filter((r) => (tab === "reports" ? !!r.report_title : true) && (!dept || r.department === dept));

  return (
    <>
      <PageHead title="Medical Records" subtitle="Recent records and attached reports" />
      <div className="filters">
        <div className="tabs" role="tablist" aria-label="Record type">
          <button role="tab" className="tab" aria-selected={tab === "all"} onClick={() => setParams({})}>All records</button>
          <button role="tab" className="tab" aria-selected={tab === "reports"} onClick={() => setParams({ tab: "reports" })}>Reports</button>
        </div>
        <div className="field"><label htmlFor="dept" className="sr-only">Department</label>
          <select id="dept" className="input" value={dept} onChange={(e) => setDept(e.target.value)}>
            <option value="">All departments</option>{departments.map((d) => <option key={d}>{d}</option>)}
          </select></div>
      </div>
      <section className="card">
        {loading ? <Loading /> : error ? <div className="card-pad"><ErrorBanner message={error} /></div> :
          rows.length === 0 ? <div className="empty">No records match.</div> : rows.map((r) => <Record key={r.id} r={r} />)}
      </section>
    </>
  );
}
