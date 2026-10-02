import { useState, type ReactNode } from "react";
import { CheckCircle2, ShieldAlert, ShieldCheck } from "lucide-react";
import type { Analysis, Metric } from "../lib/types";
import Pipeline, { usePipelineProgress } from "./Pipeline";
import Waveform from "./Waveform";
import { EmbeddingBars } from "./smallCharts";

type TraceKey = "raw" | "filtered" | "normalized";

function MetricValue({ m }: { m: Metric }) {
  const v = m.value === null ? "-" : typeof m.value === "number" ? m.value.toLocaleString("en-GB", { maximumFractionDigits: 2 }) : m.value;
  return <span className="m-val num">{v}{m.unit && m.unit !== "%" ? ` ${m.unit}` : m.unit}</span>;
}

const KIND_TAG: Record<Metric["kind"], { text: string; cls: string; title: string } | null> = {
  measured: null,
  derived: { text: "derived", cls: "", title: "Computed from the recording" },
  demonstration: { text: "demo", cls: "demo", title: "Illustrative value for demonstration purposes" },
};

/**
 * The single ECG analysis experience. It renders the server's analysis response; the verdict
 * shown here is only a display of the backend's decision.
 */
export default function AnalysisView({ analysis, animate, verdictActions }: {
  analysis: Analysis;
  animate: boolean;
  verdictActions?: ReactNode;
}) {
  const progress = usePipelineProgress(analysis.stages, animate);
  const [trace, setTrace] = useState<TraceKey>("raw");
  const auth = analysis.authentication;
  const { finished, done } = progress;

  const traces: Record<TraceKey, { t: number[]; v: number[]; units: string; title: string; note: string }> = {
    raw: { t: analysis.signal.t, v: analysis.signal.v, units: analysis.signal.units, title: "Raw signal", note: "Channel 0 as recorded." },
    filtered: { ...analysis.processed.filtered, units: analysis.signal.units, title: "Processed signal", note: analysis.processed.method.filtered },
    normalized: { ...analysis.processed.normalized, units: "z-score", title: "Normalized window", note: analysis.processed.method.normalized },
  };
  const cur = traces[trace];
  const identityMetric: Metric[] = analysis.metrics.filter((m) => m.key !== "processing_time");
  const processing = analysis.metrics.find((m) => m.key === "processing_time");
  const hasDemo = analysis.metrics.some((m) => m.kind === "demonstration") || analysis.stages.some((s) => s.timing_kind === "demonstration");

  return (
    <div className="stack" style={{ gap: 20 }}>
      {done && (
        <div className={`verdict reveal ${auth.authenticated ? "ok" : "fail"}`} role="status">
          <span className="v-icon">{auth.authenticated ? <ShieldCheck size={26} /> : <ShieldAlert size={26} />}</span>
          <div className="grow">
            <h2>{auth.authenticated ? "Identity Verified" : "Authentication Failed"}</h2>
            <p className="secondary">
              {auth.authenticated && auth.identity
                ? (auth.method === "ecg_model" ? `Recognized as ${auth.identity.name} by the ECG model` : `Welcome, ${auth.identity.name}`)
                : auth.message}
            </p>
          </div>
          {verdictActions && <div className="row wrap">{verdictActions}</div>}
        </div>
      )}

      <div className="grid split" style={{ alignItems: "start" }}>
        <div className="stack" style={{ gap: 20, minWidth: 0 }}>
          {finished >= 1 && (
            <section className="card reveal" aria-labelledby="sig-h">
              <div className="card-head">
                <div><h2 id="sig-h">ECG Signal</h2><p className="small muted">{cur.note}</p></div>
                <div className="tabs" role="tablist" aria-label="Signal view">
                  {(["raw", "filtered", "normalized"] as TraceKey[]).map((k) => (
                    <button key={k} role="tab" aria-selected={trace === k} className="tab" onClick={() => setTrace(k)}>{k === "raw" ? "Raw" : k === "filtered" ? "Processed" : "Normalized"}</button>
                  ))}
                </div>
              </div>
              <div className="card-pad">
                <Waveform
                  key={trace} t={cur.t} v={cur.v} units={cur.units} label={`${cur.title} waveform`}
                  segment={trace === "raw" ? analysis.signal.segment : null}
                  markers={trace === "filtered" ? analysis.features.r_peaks_s : undefined}
                />
                {trace === "raw" && (
                  <p className="hint" style={{ marginTop: 8 }}>
                    The shaded window ({analysis.signal.segment.start_s.toFixed(1)}-{analysis.signal.segment.end_s.toFixed(1)} s, {analysis.signal.segment.end_idx} samples) is the segment used for analysis.
                  </p>
                )}
              </div>
            </section>
          )}

          {finished >= 5 && (
            <section className="card reveal" aria-labelledby="feat-h">
              <div className="card-head">
                <div><h2 id="feat-h">Feature Visualization</h2>
                  <p className="small muted">Averaged beat and {analysis.features.dimension}-dimensional embedding</p></div>
              </div>
              <div className="card-pad grid cols-2" style={{ alignItems: "start" }}>
                <div>
                  <div className="label" style={{ marginBottom: 6 }}>Mean beat ({analysis.features.mean_beat.beats_averaged} beats, R-peak at 0 s)</div>
                  {analysis.features.mean_beat.t.length > 0
                    ? <Waveform t={analysis.features.mean_beat.t} v={analysis.features.mean_beat.v} units={analysis.signal.units} height={170} zoomable={false} label="Mean beat" />
                    : <div className="empty">Not enough complete beats</div>}
                </div>
                <div>
                  <div className="label" style={{ marginBottom: 6 }}>Embedding</div>
                  <EmbeddingBars values={analysis.features.embedding} />
                  <p className="hint">
                    {analysis.features.source === "cnn_feature_extractor"
                      ? "From the pre-trained CNN feature extractor."
                      : "Placeholder values (the feature extractor was unavailable)."} L2 norm {analysis.features.stats.l2_norm}.
                  </p>
                </div>
              </div>
            </section>
          )}
        </div>

        <div className="stack" style={{ gap: 20, minWidth: 0 }}>
          <section className="card" aria-labelledby="pipe-h">
            <div className="card-head">
              <h2 id="pipe-h">ECG Analysis Pipeline</h2>
              <span className={`badge ${done ? (auth.authenticated ? "good" : "bad") : "info"}`}>{done ? (auth.authenticated ? "Complete" : "Complete · denied") : "Running"}</span>
            </div>
            <div className="card-pad"><Pipeline stages={analysis.stages} statuses={progress.shown} /></div>
          </section>

          {done && (
            <section className="card reveal" aria-labelledby="sum-h">
              <div className="card-head"><h2 id="sum-h">Analysis Summary</h2></div>
              <div className="card-pad">
                <div className="metric-row"><span className="m-label">Identity</span><span className="m-val">{auth.identity?.name ?? "Not verified"}</span></div>
                <div className="metric-row"><span className="m-label">Authentication</span>
                  <span className="m-val" style={{ color: auth.authenticated ? "var(--good-text)" : "var(--critical-text)" }}>
                    {auth.authenticated ? <><CheckCircle2 size={14} style={{ verticalAlign: -2 }} /> Verified</> : "Denied"}
                  </span></div>
                {processing && <div className="metric-row"><span className="m-label">Processing time</span><MetricValue m={processing} /></div>}
                <div className="metric-row"><span className="m-label">Pipeline status</span><span className="m-val">Complete</span></div>
                <div className="metric-row"><span className="m-label">Pipeline version</span><span className="m-val mono">{analysis.pipeline_version}</span></div>
                {identityMetric.map((m) => {
                  const tag = KIND_TAG[m.kind];
                  return (
                    <div className="metric-row" key={m.key}>
                      <span className="m-label">{m.label}{tag && <span className={`kind-tag ${tag.cls}`} title={tag.title}>{tag.text}</span>}</span>
                      <MetricValue m={m} />
                    </div>
                  );
                })}
                <p className="hint" style={{ marginTop: 10 }}>
                  {analysis.source === "enrolled_profile"
                    ? "Visualization is the stored analysis profile for your enrolled recording: identical on every sign-in."
                    : "Visualization shows the recording you uploaded."}
                  {hasDemo && " Values tagged “demo” (including per-stage timings) are illustrative demonstration values."}
                </p>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
