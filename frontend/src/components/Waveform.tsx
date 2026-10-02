import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Minus, Plus, RotateCcw } from "lucide-react";
import { fmtTick, lowerBound, niceTicks, tipLeft, useWidth } from "./chartUtils";

interface Props {
  t: number[];
  v: number[];
  units?: string;
  height?: number;
  /** Shaded analysis window, in seconds. */
  segment?: { start_s: number; end_s: number } | null;
  /** Marker positions on the trace (seconds), e.g. detected R-peaks. */
  markers?: number[];
  /** Enable wheel-zoom, drag-pan, keyboard and buttons. */
  zoomable?: boolean;
  label: string;
}

const M = { l: 52, r: 14, t: 12, b: 34 };
const MIN_SPAN_FRACTION = 0.02;

/** Interactive ECG trace: zoom (wheel / buttons / +-), pan (drag / arrows), crosshair readout. */
export default function Waveform({ t, v, units = "mV", height = 260, segment, markers, zoomable = true, label }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const full = useMemo<[number, number]>(() => [t[0] ?? 0, t[t.length - 1] ?? 1], [t]);
  const [dom, setDom] = useState<[number, number]>(full);
  const [hover, setHover] = useState<number | null>(null);
  const drag = useRef<{ x: number; d: [number, number] } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => setDom(full), [full]);

  const iw = width - M.l - M.r;
  const ih = height - M.t - M.b;
  const x = useCallback((s: number) => M.l + ((s - dom[0]) / (dom[1] - dom[0])) * iw, [dom, iw]);

  // Visible slice (+1 point either side so the line reaches the edges)
  const { i0, i1 } = useMemo(() => {
    const a = Math.max(0, lowerBound(t, dom[0]) - 1);
    const b = Math.min(t.length - 1, lowerBound(t, dom[1]) + 1);
    return { i0: a, i1: b };
  }, [t, dom]);

  const [ymin, ymax] = useMemo(() => {
    let lo = Infinity, hi = -Infinity;
    for (let i = i0; i <= i1; i++) { if (v[i] < lo) lo = v[i]; if (v[i] > hi) hi = v[i]; }
    if (!Number.isFinite(lo)) return [-1, 1];
    const pad = (hi - lo || 1) * 0.1;
    return [lo - pad, hi + pad];
  }, [v, i0, i1]);
  const y = (a: number) => M.t + (1 - (a - ymin) / (ymax - ymin)) * ih;

  const path = useMemo(() => {
    const parts: string[] = [];
    for (let i = i0; i <= i1; i++) parts.push(`${i === i0 ? "M" : "L"}${x(t[i]).toFixed(1)},${y(v[i]).toFixed(1)}`);
    return parts.join("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t, v, i0, i1, dom, iw, ymin, ymax]);

  const clamp = useCallback((a: number, b: number): [number, number] => {
    const span = Math.min(b - a, full[1] - full[0]);
    let s = a;
    if (s < full[0]) s = full[0];
    if (s + span > full[1]) s = full[1] - span;
    return [s, s + span];
  }, [full]);

  const zoomAt = useCallback((factor: number, center: number) => {
    setDom((d) => {
      const span = (d[1] - d[0]) * factor;
      const minSpan = (full[1] - full[0]) * MIN_SPAN_FRACTION;
      const ns = Math.min(full[1] - full[0], Math.max(minSpan, span));
      const frac = (center - d[0]) / (d[1] - d[0]);
      return clamp(center - frac * ns, center - frac * ns + ns);
    });
  }, [clamp, full]);

  const pan = useCallback((delta: number) => setDom((d) => clamp(d[0] + delta, d[1] + delta)), [clamp]);

  const toTime = (clientX: number) => {
    const r = svgRef.current!.getBoundingClientRect();
    const px = ((clientX - r.left) / r.width) * width;
    return dom[0] + ((px - M.l) / iw) * (dom[1] - dom[0]);
  };

  // wheel must be non-passive to prevent page scroll while zooming
  useEffect(() => {
    const el = svgRef.current;
    if (!el || !zoomable) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      zoomAt(e.deltaY > 0 ? 1.25 : 0.8, toTime(e.clientX));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoomable, zoomAt, dom, width]);

  const onPointerMove = (e: React.PointerEvent) => {
    const tm = toTime(e.clientX);
    if (drag.current) {
      const dx = ((e.clientX - drag.current.x) / (svgRef.current!.getBoundingClientRect().width)) * width;
      const dt = -(dx / iw) * (drag.current.d[1] - drag.current.d[0]);
      setDom(clamp(drag.current.d[0] + dt, drag.current.d[1] + dt));
      return;
    }
    const i = Math.min(t.length - 1, Math.max(0, lowerBound(t, tm)));
    const j = i > 0 && Math.abs(t[i - 1] - tm) < Math.abs(t[i] - tm) ? i - 1 : i; // snap to nearest sample
    setHover(j);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (!zoomable) return;
    const span = dom[1] - dom[0];
    if (e.key === "ArrowLeft") { e.preventDefault(); pan(-span * 0.2); }
    else if (e.key === "ArrowRight") { e.preventDefault(); pan(span * 0.2); }
    else if (e.key === "+" || e.key === "=") zoomAt(0.7, dom[0] + span / 2);
    else if (e.key === "-") zoomAt(1.4, dom[0] + span / 2);
    else if (e.key === "0") setDom(full);
  };

  const xt = niceTicks(dom[0], dom[1], Math.max(3, Math.floor(iw / 90)));
  const yt = niceTicks(ymin, ymax, 4);
  const zoomed = dom[1] - dom[0] < full[1] - full[0] - 1e-9;
  const hx = hover !== null ? x(t[hover]) : null;
  const visibleMarkers = (markers ?? []).filter((m) => m >= dom[0] && m <= dom[1]);
  const segX0 = segment ? Math.max(M.l, x(segment.start_s)) : 0;
  const segX1 = segment ? Math.min(M.l + iw, x(segment.end_s)) : 0;
  const clipId = useMemo(() => `clip-${Math.random().toString(36).slice(2, 8)}`, []);

  return (
    <div className="chart" ref={ref}>
      {zoomable && (
        <div className="wave-toolbar" style={{ marginBottom: 6 }}>
          <button className="icon-btn" type="button" aria-label="Zoom in" onClick={() => zoomAt(0.6, dom[0] + (dom[1] - dom[0]) / 2)}><Plus size={16} /></button>
          <button className="icon-btn" type="button" aria-label="Zoom out" onClick={() => zoomAt(1.6, dom[0] + (dom[1] - dom[0]) / 2)}><Minus size={16} /></button>
          <button className="icon-btn" type="button" aria-label="Reset zoom" onClick={() => setDom(full)} disabled={!zoomed}><RotateCcw size={15} /></button>
          <span className="hint">Scroll to zoom, drag to pan{segment ? " · shaded area = analysis window" : ""}</span>
        </div>
      )}
      <svg
        ref={svgRef} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label} tabIndex={zoomable ? 0 : -1}
        onKeyDown={onKey} style={{ cursor: zoomable ? (drag.current ? "grabbing" : "crosshair") : "default", touchAction: "none" }}
        onPointerDown={(e) => { if (!zoomable) return; (e.currentTarget as Element).setPointerCapture(e.pointerId); drag.current = { x: e.clientX, d: dom }; }}
        onPointerUp={() => { drag.current = null; }}
        onPointerMove={onPointerMove} onPointerLeave={() => setHover(null)}
        onDoubleClick={() => setDom(full)}
      >
        <defs><clipPath id={clipId}><rect x={M.l} y={M.t} width={Math.max(0, iw)} height={ih} /></clipPath></defs>
        {yt.map((tv) => (
          <g key={`y${tv}`}>
            <line className="grid-line" x1={M.l} x2={M.l + iw} y1={y(tv)} y2={y(tv)} />
            <text className="tick" x={M.l - 8} y={y(tv) + 4} textAnchor="end">{fmtTick(tv)}</text>
          </g>
        ))}
        {xt.map((tv) => (
          <g key={`x${tv}`}>
            <line className="grid-line" x1={x(tv)} x2={x(tv)} y1={M.t} y2={M.t + ih} />
            <text className="tick" x={x(tv)} y={height - 14} textAnchor="middle">{fmtTick(tv)}</text>
          </g>
        ))}
        <line className="axis-line" x1={M.l} x2={M.l + iw} y1={M.t + ih} y2={M.t + ih} />
        <text className="axis-title" x={M.l + iw / 2} y={height - 1} textAnchor="middle">Time (s)</text>
        <text className="axis-title" transform={`translate(12 ${M.t + ih / 2}) rotate(-90)`} textAnchor="middle">Amplitude ({units})</text>

        <g clipPath={`url(#${clipId})`}>
          {segment && segX1 > segX0 && <rect x={segX0} y={M.t} width={segX1 - segX0} height={ih} fill="var(--series-1)" opacity={0.08} />}
          <path className="line" d={path} stroke="var(--series-1)" />
          {visibleMarkers.map((m) => {
            const i = Math.min(t.length - 1, lowerBound(t, m));
            return <circle key={m} cx={x(m)} cy={y(v[i])} r={4} fill="var(--series-2)" stroke="var(--surface)" strokeWidth={2} />;
          })}
        </g>
        {hover !== null && hx !== null && hx >= M.l && hx <= M.l + iw && (
          <>
            <line className="hover-line" x1={hx} x2={hx} y1={M.t} y2={M.t + ih} />
            <circle cx={hx} cy={y(v[hover])} r={4} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2} />
          </>
        )}
      </svg>
      {hover !== null && hx !== null && hx >= M.l && hx <= M.l + iw && (
        <div className="chart-tip" style={{ left: tipLeft(hx, width), top: Math.max(30, y(v[hover]) + (zoomable ? 38 : 0)) }}>
          <div className="tip-head">{t[hover].toFixed(3)} s</div>
          <div className="tip-row"><span><span className="tip-key" style={{ background: "var(--series-1)" }} />Amplitude</span><span className="tip-val">{v[hover].toFixed(3)} {units}</span></div>
        </div>
      )}
      {markers && markers.length > 0 && (
        <div className="legend" style={{ marginTop: 6 }}>
          <span><span className="key line" style={{ background: "var(--series-1)" }} />Signal</span>
          <span><span className="key" style={{ background: "var(--series-2)", borderRadius: "50%" }} />Detected R-peaks</span>
        </div>
      )}
    </div>
  );
}
