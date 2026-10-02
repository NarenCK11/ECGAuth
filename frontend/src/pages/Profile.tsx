import { useState } from "react";
import { Copy } from "lucide-react";
import { api } from "../lib/api";
import { useFetch } from "../lib/hooks";
import { fmtDate, fmtDateTime } from "../lib/format";
import type { Profile as ProfileT } from "../lib/types";
import { ErrorBanner, Loading, PageHead, StatusBadge } from "../components/ui";

export default function Profile() {
  const { data, loading, error } = useFetch(() => api.get<ProfileT>("/api/users/me"), []);
  const [copied, setCopied] = useState(false);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBanner message={error ?? "Could not load profile."} />;
  const { user, enrollment } = data;
  return (
    <>
      <PageHead title="Profile" subtitle="Your account and enrolled ECG" />
      <div className="grid cols-2" style={{ alignItems: "start" }}>
        <section className="card">
          <div className="card-head"><h2>Account</h2><StatusBadge status={user.status} /></div>
          <dl className="kv card-pad">
            <dt>Full name</dt><dd>{user.full_name}</dd>
            <dt>Patient ID</dt><dd><strong>{user.patient_id}</strong></dd>
            <dt>Username</dt><dd>{user.username}</dd>
            <dt>Email</dt><dd>{user.email}</dd>
            <dt>Date of birth</dt><dd>{fmtDate(user.date_of_birth)}</dd>
            <dt>Member since</dt><dd>{fmtDate(user.created_at)}</dd>
            <dt>Account UUID</dt>
            <dd className="row" style={{ gap: 6 }}><span className="mono">{user.id}</span>
              <button className="icon-btn" aria-label="Copy UUID" onClick={() => { void navigator.clipboard?.writeText(user.id); setCopied(true); }}><Copy size={15} /></button>
              {copied && <span className="hint">Copied</span>}</dd>
          </dl>
        </section>
        <section className="card">
          <div className="card-head"><h2>ECG enrollment</h2></div>
          <dl className="kv card-pad">
            <dt>Reference</dt><dd className="mono">{enrollment?.reference ?? "-"}</dd>
            <dt>Enrolled on</dt><dd>{enrollment ? fmtDateTime(enrollment.enrolled_at) : "-"}</dd>
            <dt>Recording</dt><dd>{enrollment?.original_filename ?? "-"}</dd>
            <dt>Sampling rate</dt><dd>{enrollment?.sampling_rate ? `${enrollment.sampling_rate} Hz` : "-"}</dd>
            <dt>Samples</dt><dd>{enrollment?.sample_count?.toLocaleString("en-GB") ?? "-"}</dd>
            <dt>Verified sign-ins</dt><dd>{data.authentication_count}</dd>
            <dt>Last verified</dt><dd>{data.last_authenticated_at ? fmtDateTime(data.last_authenticated_at) : "-"}</dd>
          </dl>
          <p className="hint" style={{ padding: "0 20px 20px" }}>Only SHA-256 fingerprints of your files are stored. The raw recording is not kept.</p>
        </section>
      </div>
    </>
  );
}
