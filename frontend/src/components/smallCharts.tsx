import { useState } from "react";
import { fmtTick, niceTicks, tipLeft, useWidth } from "./chartUtils";

/** 128-D embedding as columns from a zero baseline (sign = direction; one hue). */
export function EmbeddingBars({ values }: { values: number[] }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const H = 150, M = { l: 36, r: 6, t: 8, b: 20 };
  const lim = Math.max(0.001, ...values.map((v) => Math.abs(v)));
  const ticks = niceTicks(-lim, lim, 4);
  const top = Math.max(...ticks.map(Math.abs), lim);
  const iw = width - M.l - M.r, ih = H - M.t - M.b;
  const band = iw / values.length;
  const bw = Math.max(1.5, Math.min(24, band - 2)); // 2px surface gap between neighbours
  const y = (v: number) => M.t + ih / 2 - (v / top) * (ih / 2);
  return (
    <div className="chart" ref={ref}>
      <svg viewBox={`0 0 ${width} ${H}`} role="img" aria-label={`${values.length}-dimensional feature embedding`} onPointerLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}><line className="grid-line" x1={M.l} x2={M.l + iw} y1={y(t)} y2={y(t)} /><text className="tick" x={M.l - 6} y={y(t) + 4} textAnchor="end">{fmtTick(t)}</text></g>
        ))}
        <line className="axis-line" x1={M.l} x2={M.l + iw} y1={y(0)} y2={y(0)} />
        {values.map((v, i) => {
          const cx = M.l + band * i + band / 2;
          return (
            <g key={i} onPointerEnter={() => setHover(i)}>
              <rect x={M.l + band * i} y={M.t} width={band} height={ih} fill="transparent" />
              <rect x={cx - bw / 2} y={Math.min(y(0), y(v))} width={bw} height={Math.max(1, Math.abs(y(v) - y(0)))} rx={Math.min(2, bw / 2)}
                fill="var(--series-1)" opacity={hover === null || hover === i ? 1 : 0.55} />
            </g>
          );
        })}
        <text className="tick" x={M.l} y={H - 4}>0</text>
        <text className="tick" x={M.l + iw} y={H - 4} textAnchor="end">{values.length - 1}</text>
        <text className="axis-title" x={M.l + iw / 2} y={H - 4} textAnchor="middle">Feature index</text>
      </svg>
      {hover !== null && (
        <div className="chart-tip" style={{ left: tipLeft(M.l + band * hover + band / 2, width), top: Math.max(34, y(values[hover])) }}>
          <div className="tip-head">Feature {hover}</div>
          <div className="tip-row"><span className="tip-val num">{values[hover].toFixed(3)}</span></div>
        </div>
      )}
    </div>
  );
}

/** Horizontal bars with the value at the tip. Used for ranked breakdowns. */
export function BarList({ rows, empty = "No data yet" }: { rows: { label: string; value: number; sub?: string }[]; empty?: string }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (rows.length === 0) return <div className="empty">{empty}</div>;
  return (
    <div className="stack" style={{ gap: 12 }}>
      {rows.map((r) => (
        <div key={r.label} title={`${r.label}: ${r.value}`}>
          <div className="row spread small" style={{ marginBottom: 4 }}>
            <span>{r.label}{r.sub && <span className="muted"> · {r.sub}</span>}</span>
            <span className="num" style={{ fontWeight: 620 }}>{r.value.toLocaleString("en-GB")}</span>
          </div>
          <div className="meter" style={{ height: 10 }}><i style={{ width: `${Math.max(2, (r.value / max) * 100)}%` }} /></div>
        </div>
      ))}
    </div>
  );
}
