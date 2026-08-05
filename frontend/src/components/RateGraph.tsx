/**
 * Live continuous-rate chart for the “Trace” avatar option.
 *
 * Renders the last 5 minutes from the session-wide rate history store
 * (so switching avatars does not reset the plot).
 * Thin blue stroke; multi-stage smoothing for a continuous glide.
 * Y-axis fixed 0–30 with marks every 10; red dotted line at 10.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  RATE_WINDOW_S,
  capRateForGraph,
  getRateEma,
  getRateSamples,
  subscribeRateHistory,
  type RateSample,
} from "../hooks/rateHistory";

const AVG_HALF_S = 2.4;
const DRAW_POINTS = 240;
const GAUSS_RADIUS = 4;
const TENSION = 0.14;
const Y_MAX = 30;
const Y_TICKS = [10, 20, 30] as const;
const LOW_RATE_LINE = 10;
const PAD = { top: 28, right: 12, bottom: 20, left: 28 };

export interface RateGraphProps {
  faceFound: boolean;
  lastBlinkAt: number;
}

function bpmAt(arr: readonly RateSample[], t: number): number | null {
  if (arr.length === 0) return null;
  if (t <= arr[0].t) return arr[0].bpm;
  if (t >= arr[arr.length - 1].t) return arr[arr.length - 1].bpm;

  let lo = 0;
  let hi = arr.length - 1;
  while (lo + 1 < hi) {
    const mid = (lo + hi) >> 1;
    if (arr[mid].t <= t) lo = mid;
    else hi = mid;
  }
  const a = arr[lo];
  const b = arr[hi];
  const span = b.t - a.t;
  if (span <= 0) return b.bpm;
  let u = (t - a.t) / span;
  u = u * u * (3 - 2 * u);
  return a.bpm + (b.bpm - a.bpm) * u;
}

function averagedBpm(
  arr: readonly RateSample[],
  t: number,
  halfMs: number,
): number | null {
  if (arr.length === 0) return null;
  const t0 = t - halfMs;
  const t1 = t + halfMs;
  const sigma = halfMs / 2.2;
  const twoSigma2 = 2 * sigma * sigma;
  let sum = 0;
  let wsum = 0;
  for (const s of arr) {
    if (s.t < t0) continue;
    if (s.t > t1) break;
    const d = s.t - t;
    const w = Math.exp(-(d * d) / twoSigma2);
    sum += s.bpm * w;
    wsum += w;
  }
  if (wsum > 0) return sum / wsum;
  return bpmAt(arr, t);
}

function blurYs(ys: number[], radius: number): number[] {
  if (ys.length < 3 || radius < 1) return ys;
  const out = new Array<number>(ys.length);
  const sigma = radius / 1.8;
  const twoSigma2 = 2 * sigma * sigma;
  for (let i = 0; i < ys.length; i++) {
    let sum = 0;
    let wsum = 0;
    const a = Math.max(0, i - radius);
    const b = Math.min(ys.length - 1, i + radius);
    for (let j = a; j <= b; j++) {
      const d = j - i;
      const w = Math.exp(-(d * d) / twoSigma2);
      sum += ys[j] * w;
      wsum += w;
    }
    out[i] = sum / wsum;
  }
  out[out.length - 1] = ys[ys.length - 1];
  if (out.length > 1) {
    out[out.length - 2] =
      ys[ys.length - 2] * 0.4 + out[out.length - 2] * 0.6;
  }
  return out;
}

/** Build a smooth path; falls back to polyline if needed. */
function smoothPath(pts: { x: number; y: number }[]): string {
  if (pts.length === 0) return "";
  if (pts.length === 1) {
    // Degenerate: tiny horizontal tick so a lone point is still visible.
    const p = pts[0];
    return `M ${(p.x - 2).toFixed(2)} ${p.y.toFixed(2)} L ${(p.x + 2).toFixed(2)} ${p.y.toFixed(2)}`;
  }
  if (pts.length === 2) {
    return `M ${pts[0].x.toFixed(2)} ${pts[0].y.toFixed(2)} L ${pts[1].x.toFixed(2)} ${pts[1].y.toFixed(2)}`;
  }

  // Prefer a reliable polyline when the x-span is tiny (early trail).
  const xSpan = pts[pts.length - 1].x - pts[0].x;
  if (xSpan < 4) {
    let d = `M ${pts[0].x.toFixed(2)} ${pts[0].y.toFixed(2)}`;
    for (let i = 1; i < pts.length; i++) {
      d += ` L ${pts[i].x.toFixed(2)} ${pts[i].y.toFixed(2)}`;
    }
    return d;
  }

  const k = TENSION;
  let d = `M ${pts[0].x.toFixed(2)} ${pts[0].y.toFixed(2)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    const c1x = p1.x + (p2.x - p0.x) * k;
    const c1y = p1.y + (p2.y - p0.y) * k;
    const c2x = p2.x - (p3.x - p1.x) * k;
    const c2y = p2.y - (p3.y - p1.y) * k;
    d += ` C ${c1x.toFixed(2)} ${c1y.toFixed(2)}, ${c2x.toFixed(2)} ${c2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
  }
  return d;
}

export function RateGraph({ faceFound, lastBlinkAt }: RateGraphProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 320, h: 200 });
  const [frame, setFrame] = useState(0);
  const [blinkFlash, setBlinkFlash] = useState(false);
  const prevBlinkAt = useRef(0);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect;
      if (!r) return;
      const w = Math.max(120, Math.round(r.width));
      const h = Math.max(90, Math.round(r.height));
      setSize((s) => (s.w === w && s.h === h ? s : { w, h }));
    });
    ro.observe(el);
    // Immediate measure (ResizeObserver can lag one frame in webviews).
    const rect = el.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      setSize({
        w: Math.max(120, Math.round(rect.width)),
        h: Math.max(90, Math.round(rect.height)),
      });
    }
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    return subscribeRateHistory(() => {
      setFrame((n) => (n + 1) % 1_000_000);
    });
  }, []);

  useEffect(() => {
    if (!lastBlinkAt || lastBlinkAt === prevBlinkAt.current) return;
    prevBlinkAt.current = lastBlinkAt;
    setBlinkFlash(true);
    const id = window.setTimeout(() => setBlinkFlash(false), 420);
    return () => window.clearTimeout(id);
  }, [lastBlinkAt]);

  const { pathD, nowBpm } = useMemo(() => {
    void frame;
    const now = performance.now();
    const arr = getRateSamples();
    const halfMs = AVG_HALF_S * 1000;
    const tStart = now - RATE_WINDOW_S * 1000;

    const { w, h } = size;
    const plotW = Math.max(1, w - PAD.left - PAD.right);
    const plotH = Math.max(1, h - PAD.top - PAD.bottom);

    const xOf = (t: number) =>
      PAD.left + ((t - tStart) / (RATE_WINDOW_S * 1000)) * plotW;
    const yOf = (bpm: number) =>
      PAD.top + plotH - (capRateForGraph(bpm) / Y_MAX) * plotH;

    const pts: { x: number; y: number }[] = [];

    if (arr.length > 0) {
      // First sample time (never left of −5m).
      const dataStart = Math.max(tStart, arr[0].t);
      const dataEnd = now;

      // Always build a dense series from first sample → now so a trail exists.
      const spanMs = Math.max(1, dataEnd - dataStart);
      const n = Math.max(
        8,
        Math.min(DRAW_POINTS, Math.ceil(spanMs / 50) + 2),
      );

      const xs: number[] = [];
      const ys: number[] = [];
      for (let i = 0; i < n; i++) {
        const u = n === 1 ? 1 : i / (n - 1);
        const t = dataStart + u * spanMs;
        // Prefer raw interp for the trail; light average keeps it smooth.
        const v =
          averagedBpm(arr, t, halfMs) ??
          bpmAt(arr, t) ??
          getRateEma();
        const x = Math.max(PAD.left, Math.min(PAD.left + plotW, xOf(t)));
        xs.push(x);
        ys.push(yOf(v));
      }

      const smoothY = blurYs(ys, GAUSS_RADIUS);
      for (let i = 0; i < xs.length; i++) {
        pts.push({ x: xs[i], y: smoothY[i] });
      }

      // Pin head to live smoothed value at the right edge.
      if (pts.length > 0) {
        pts[pts.length - 1] = {
          x: PAD.left + plotW,
          y: yOf(getRateEma()),
        };
      }
    }

    return {
      pathD: smoothPath(pts),
      nowBpm: getRateEma(),
    };
  }, [frame, size]);

  const { w, h } = size;
  const plotW = Math.max(1, w - PAD.left - PAD.right);
  const plotH = Math.max(1, h - PAD.top - PAD.bottom);
  const yOf = (bpm: number) =>
    PAD.top + plotH - (capRateForGraph(bpm) / Y_MAX) * plotH;

  const bandTop = yOf(20);
  const bandBot = yOf(15);
  const lowY = yOf(LOW_RATE_LINE);
  const headX = PAD.left + plotW;
  const headY = yOf(nowBpm);
  const displayBpm = capRateForGraph(nowBpm);

  return (
    <div
      className="rate-graph"
      ref={wrapRef}
      aria-label="Continuous blink rate, last 5 minutes"
    >
      <div
        className={`rate-graph__blink-dot ${blinkFlash ? "is-flash" : ""} ${
          faceFound ? "" : "is-idle"
        }`}
        title="Blink indicator"
        aria-hidden
      />

      <div className="rate-graph__legend" aria-hidden>
        <span className="rate-graph__legend-item rate-graph__legend-item--rate">
          Rate
        </span>
        <span className="rate-graph__legend-item rate-graph__legend-item--reg muted">
          Regularity
        </span>
      </div>

      <div className="rate-graph__live" aria-live="polite">
        <span className="rate-graph__live-value">
          {faceFound ? displayBpm.toFixed(1) : "—"}
        </span>
        <span className="rate-graph__live-unit">/min</span>
      </div>

      <svg
        className="rate-graph__svg"
        width={w}
        height={h}
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
      >
        <rect
          x={PAD.left}
          y={bandTop}
          width={plotW}
          height={Math.max(0, bandBot - bandTop)}
          className="rate-graph__target-band"
        />

        {Y_TICKS.map((v) => {
          const y = yOf(v);
          return (
            <g key={v}>
              <line
                x1={PAD.left}
                y1={y}
                x2={PAD.left + plotW}
                y2={y}
                className="rate-graph__grid"
              />
              <text
                x={PAD.left - 5}
                y={y + 3}
                textAnchor="end"
                className="rate-graph__axis-label"
              >
                {v}
              </text>
            </g>
          );
        })}
        <text
          x={PAD.left - 5}
          y={PAD.top + plotH + 3}
          textAnchor="end"
          className="rate-graph__axis-label"
        >
          0
        </text>

        <line
          x1={PAD.left}
          y1={lowY}
          x2={PAD.left + plotW}
          y2={lowY}
          className="rate-graph__low-line"
        />

        <line
          x1={PAD.left}
          y1={PAD.top + plotH}
          x2={PAD.left + plotW}
          y2={PAD.top + plotH}
          className="rate-graph__axis"
        />

        {/* No clipPath — some desktop webviews hide clipped strokes. */}
        {pathD ? (
          <>
            <path
              d={pathD}
              fill="none"
              className="rate-graph__line rate-graph__line--glow"
            />
            <path
              d={pathD}
              fill="none"
              className="rate-graph__line rate-graph__line--rate"
            />
          </>
        ) : null}

        {faceFound ? (
          <circle cx={headX} cy={headY} r={3} className="rate-graph__head" />
        ) : null}

        <text
          x={PAD.left}
          y={h - 5}
          className="rate-graph__axis-label"
          textAnchor="start"
        >
          −5m
        </text>
        <text
          x={PAD.left + plotW}
          y={h - 5}
          className="rate-graph__axis-label"
          textAnchor="end"
        >
          now
        </text>
      </svg>

      {!faceFound && (
        <div className="rate-graph__empty">
          Face the camera to start the trace
        </div>
      )}
    </div>
  );
}
