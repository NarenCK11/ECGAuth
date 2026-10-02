import { useEffect, useState } from "react";
import { Check, Circle, X } from "lucide-react";
import type { Stage, StageStatus } from "../lib/types";

/** Same cadence for every attempt: each stage spends STEP_MS "processing", in fixed order. */
export const STEP_MS = 420;

/**
 * Reveals the (already final) server-side stage statuses one at a time:
 * pending -> processing -> completed/failed. Returns the number of stages that have finished.
 */
export function usePipelineProgress(stages: Stage[] | undefined, animate: boolean): { shown: StageStatus[]; finished: number; done: boolean } {
  const total = stages?.length ?? 0;
  const [finished, setFinished] = useState(animate ? 0 : total);
  const [processing, setProcessing] = useState(animate && total > 0);

  useEffect(() => {
    if (!animate || total === 0) { setFinished(total); setProcessing(false); return; }
    setFinished(0);
    setProcessing(true);
    let n = 0;
    const timer = setInterval(() => {
      n += 1;
      setFinished(n);
      if (n >= total) { clearInterval(timer); setProcessing(false); }
    }, STEP_MS);
    return () => clearInterval(timer);
  }, [animate, total, stages]);

  const shown = (stages ?? []).map<StageStatus>((s, i) => {
    if (i < finished) return s.status;
    if (i === finished && processing) return "processing";
    return "pending";
  });
  return { shown, finished, done: finished >= total && total > 0 };
}

function Dot({ status }: { status: StageStatus }) {
  if (status === "completed") return <Check size={17} strokeWidth={3} />;
  if (status === "failed") return <X size={17} strokeWidth={3} />;
  if (status === "processing") return <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2.5 }} />;
  return <Circle size={9} />;
}

const STATUS_WORD: Record<StageStatus, string> = { pending: "Pending", processing: "Processing", completed: "Completed", failed: "Failed" };

export default function Pipeline({ stages, statuses }: { stages: Stage[]; statuses: StageStatus[] }) {
  return (
    <ol className="pipeline" aria-label="ECG analysis pipeline" style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {stages.map((s, i) => {
        const st = statuses[i] ?? "pending";
        return (
          <li key={s.id} className={`stage s-${st}`} aria-live="polite">
            <span className="stage-dot"><Dot status={st} /></span>
            <div>
              <div className="stage-title">{i + 1}. {s.label}<span className="sr-only"> - {STATUS_WORD[st]}</span></div>
              <div className="stage-detail">{st === "pending" ? s.description : st === "processing" ? s.description : s.detail}</div>
            </div>
            <div className="stage-time num">{st === "completed" || st === "failed" ? `${s.duration_ms} ms` : st === "processing" ? "…" : ""}</div>
          </li>
        );
      })}
    </ol>
  );
}
