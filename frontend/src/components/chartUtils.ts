import { useEffect, useRef, useState } from "react";

/** Round tick values ("nice" numbers) covering [min, max]. */
export function niceTicks(min: number, max: number, count = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1];
  if (min === max) { min -= 1; max += 1; }
  const span = max - min;
  const raw = span / Math.max(1, count);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const start = Math.ceil(min / step) * step;
  const out: number[] = [];
  for (let v = start; v <= max + step * 1e-9; v += step) out.push(Math.abs(v) < step * 1e-9 ? 0 : +v.toFixed(10));
  return out;
}

export function fmtTick(v: number): string {
  const a = Math.abs(v);
  if (a >= 1000) return v.toLocaleString("en-GB");
  if (a >= 10 || Number.isInteger(v)) return String(+v.toFixed(1));
  return String(+v.toFixed(2));
}

/** Track an element's width so SVG charts can render at their real pixel size. */
export function useWidth<T extends HTMLElement>(fallback = 640): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setW(Math.max(200, Math.floor(entry.contentRect.width))));
    ro.observe(el);
    setW(Math.max(200, Math.floor(el.getBoundingClientRect().width)));
    return () => ro.disconnect();
  }, []);
  return [ref as React.RefObject<T>, w];
}

/** Index of the first element >= x in a sorted array. */
export function lowerBound(arr: number[], x: number): number {
  let lo = 0, hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (arr[mid] < x) lo = mid + 1; else hi = mid;
  }
  return lo;
}

/** Path with only the top corners rounded (bars grow from a square baseline). */
export function topRoundedRect(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.max(0, Math.min(r, w / 2, h));
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}

/** Keep a centred tooltip fully inside the chart: returns its left offset in px. */
export function tipLeft(px: number, chartWidth: number, half = 90): number {
  return Math.min(Math.max(px, half), Math.max(half, chartWidth - half));
}
