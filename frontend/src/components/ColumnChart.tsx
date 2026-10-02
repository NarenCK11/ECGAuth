import { useMemo, useState } from "react";
import { fmtTick, niceTicks, tipLeft, topRoundedRect, useWidth } from "./chartUtils";

export interface ColSeries { name: string; color: string }
export interface ColDatum { label: string; tip: string; values: number[] }

interface Props {
  series: ColSeries[];
  data: ColDatum[];
  height?: number;
  /** Show every Nth x label. */
  labelEvery?: number;
  title: string;
}

const M = { l: 40, r: 8, t: 10, b: 26 };
const GAP = 2;      // surface gap between stacked segments
const MAX_BAR = 24; // never fill the slot

/** Stacked columns with a per-column tooltip, legend (>=2 series) and a table view. */
export default function ColumnChart({ series, data, height = 220, labelEvery = 1, title }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const [table, setTable] = useState(false);

  const totals = data.map((d) => d.values.reduce((a, b) => a + b, 0));
  const ymax = Math.max(1, ...totals);
  const ticks = useMemo(() => niceTicks(0, ymax, 4).filter((t) => Number.isInteger(t)), [ymax]);
  const top = Math.max(...ticks, ymax);
  const iw = width - M.l - M.r;
  const ih = height - M.t - M.b;
  const band = iw / Math.max(1, data.length);
  const bw = Math.min(MAX_BAR, band * 0.6);
  // Thin out x labels so they never collide, whatever the width (labelEvery is only a minimum).
  const labelPx = Math.max(...data.map((d) => d.label.length), 1) * 6.5 + 12;
  const every = Math.max(labelEvery, Math.ceil(labelPx / band));
  const y = (v: number) => M.t + ih - (v / top) * ih;

  return (
    <div className="chart" ref={ref}>
      <div className="row spread" style={{ marginBottom: 8 }}>
        {series.length > 1 ? (
          <div className="legend">{series.map((s) => <span key={s.name}><span className="key" style={{ background: s.color }} />{s.name}</span>)}</div>
        ) : <span />}
        <button className="btn sm ghost" type="button" onClick={() => setTable((t) => !t)}>{table ? "View chart" : "View as table"}</button>
      </div>
      {table ? (
        <div className="table-wrap" style={{ maxHeight: height + 40, overflowY: "auto" }}>
          <table className="table">
            <thead><tr><th>{title}</th>{series.map((s) => <th key={s.name} className="num">{s.name}</th>)}</tr></thead>
            <tbody>{data.map((d) => <tr key={d.label}><td>{d.tip}</td>{d.values.map((v, i) => <td key={i} className="num">{v}</td>)}</tr>)}</tbody>
          </table>
        </div>
      ) : (
        <>
          <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title} onPointerLeave={() => setHover(null)}>
            {ticks.map((tv) => (
              <g key={tv}>
                <line className="grid-line" x1={M.l} x2={M.l + iw} y1={y(tv)} y2={y(tv)} />
                <text className="tick" x={M.l - 8} y={y(tv) + 4} textAnchor="end">{fmtTick(tv)}</text>
              </g>
            ))}
            <line className="axis-line" x1={M.l} x2={M.l + iw} y1={y(0)} y2={y(0)} />
            {data.map((d, i) => {
              const cx = M.l + band * i + band / 2;
              let acc = 0;
              const segs = d.values.map((v, si) => {
                const y0 = y(acc), y1 = y(acc + v);
                acc += v;
                return { v, si, y: y1, h: Math.max(0, y0 - y1 - (si > 0 ? GAP : 0)) };
              });
              const lastNonZero = d.values.reduce((a, v, si) => (v > 0 ? si : a), -1);
              return (
                <g key={d.label} opacity={hover !== null && hover !== i ? 0.55 : 1} style={{ transition: "opacity .12s" }}>
                  {segs.filter((s) => s.v > 0).map((s) => (
                    <path key={s.si} d={s.si === lastNonZero ? topRoundedRect(cx - bw / 2, s.y, bw, s.h, 4) : `M${cx - bw / 2},${s.y}h${bw}v${s.h}h${-bw}Z`}
                      fill={series[s.si].color} />
                  ))}
                  {i % every === 0 &&<text className="tick" x={cx} y={height - 8} textAnchor="middle">{d.label}</text>}
                  {/* hit target is the whole band, far larger than the mark */}
                  <rect x={M.l + band * i} y={M.t} width={band} height={ih + M.b} fill="transparent" tabIndex={0}
                    aria-label={`${d.tip}: ${d.values.map((v, k) => `${series[k].name} ${v}`).join(", ")}`}
                    onPointerEnter={() => setHover(i)} onFocus={() => setHover(i)} onBlur={() => setHover(null)} />
                </g>
              );
            })}
          </svg>
          {hover !== null && (
            <div className="chart-tip" style={{ left: tipLeft(M.l + band * hover + band / 2, width), top: Math.max(40, y(totals[hover])) }}>
              <div className="tip-head">{data[hover].tip}</div>
              {series.map((s, i) => (
                <div className="tip-row" key={s.name}>
                  <span><span className="tip-key" style={{ background: s.color }} />{s.name}</span>
                  <span className="tip-val num">{data[hover].values[i]}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
