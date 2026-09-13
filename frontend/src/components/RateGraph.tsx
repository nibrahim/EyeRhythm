/**
 * Live Ocular Rhythm Index chart for the “Trace” avatar option.
 *
 * Renders the last 5 minutes from the session-wide ORI history store
 * (so switching avatars does not reset the plot).
 * Thin blue stroke; multi-stage smoothing for a continuous glide.
 * Y-axis: ORI 0–100 (marks every 25; red dotted line at the alert 50).
 * Time runs now→−5m (now on the left). The line cuts on no-face / off-screen.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
} from "react";
import {
  RATE_WINDOW_S,
  capOriForGraph,
  getOriEma,
  getRateSamples,
  subscribeRateHistory,
  type RateSample,
} from "../hooks/rateHistory";
import { formatBpm } from "../utils/format";

// How far (seconds) each plotted point averages neighbouring samples.
const AVG_HALF_S = 2.4;
// Maximum dots we sample across the 5-minute window (keeps drawing cheap).
const DRAW_POINTS = 240;
const GAUSS_RADIUS = 4;
const TENSION = 0.14;
// Vertical scale is ORI 0 at the bottom, 100 at the top.
const Y_MAX = 100;
const Y_TICKS = [25, 50, 75, 100] as const;
const DEFAULT_ALERT_ORI = 50;
const GOOD_ORI_MIN = 70;
// Empty margin so axis labels are not clipped.
const PAD = { top: 28, right: 14, bottom: 28, left: 28 };

export interface RateGraphProps {
  faceFound: boolean;
  lastBlinkAt: number;
  /** Live Settings dock value — red dotted line. */
  alertOri?: number;
}

function isLiveSample(
  s: RateSample | undefined,
): s is RateSample & { ori: number } {
  // A “live” sample has a real ORI and a face looking at the screen.
  return Boolean(s && s.present && s.ori !== null && Number.isFinite(s.ori));
}

function nearestSample(
  arr: readonly RateSample[],
  t: number,
): RateSample | undefined {
  // Binary search: the history is always sorted by time.
  if (arr.length === 0) return undefined;
  if (t <= arr[0].t) return arr[0];
  if (t >= arr[arr.length - 1].t) return arr[arr.length - 1];
  let lo = 0;
  let hi = arr.length - 1;
  while (lo + 1 < hi) {
    const mid = (lo + hi) >> 1;
    if (arr[mid].t <= t) lo = mid;
    else hi = mid;
  }
  return t - arr[lo].t <= arr[hi].t - t ? arr[lo] : arr[hi];
}

/** True when the trail should be cut at t (no-face, looking down, or no ORI). */
function isAbsentAt(arr: readonly RateSample[], t: number): boolean {
  const s = nearestSample(arr, t);
  return !isLiveSample(s);
}

/** ORI at time `t`, smoothly blended between the two nearest live samples. */
function oriAt(arr: readonly RateSample[], t: number): number | null {
  if (arr.length === 0) return null;
  if (t <= arr[0].t) return isLiveSample(arr[0]) ? arr[0].ori : null;
  if (t >= arr[arr.length - 1].t) {
    return isLiveSample(arr[arr.length - 1]) ? arr[arr.length - 1].ori : null;
  }

  let lo = 0;
  let hi = arr.length - 1;
  while (lo + 1 < hi) {
    const mid = (lo + hi) >> 1;
    if (arr[mid].t <= t) lo = mid;
    else hi = mid;
  }
  const a = arr[lo];
  const b = arr[hi];
  if (!isLiveSample(a) || !isLiveSample(b)) return null;
  const span = b.t - a.t;
  if (span <= 0) return b.ori;
  let u = (t - a.t) / span;
  u = u * u * (3 - 2 * u);
  return a.ori + (b.ori - a.ori) * u;
}

/** Weighted average of nearby samples so the line glides instead of stepping. */
function averagedOri(
  arr: readonly RateSample[],
  t: number,
  halfMs: number,
): number | null {
  if (arr.length === 0) return null;
  if (oriAt(arr, t) === null) return null;
  const t0 = t - halfMs;
  const t1 = t + halfMs;
  const sigma = halfMs / 2.2;
  const twoSigma2 = 2 * sigma * sigma;
  let sum = 0;
  let wsum = 0;
  for (const s of arr) {
    if (s.t < t0) continue;
    if (s.t > t1) break;
    if (!isLiveSample(s)) continue;
    const d = s.t - t;
    const w = Math.exp(-(d * d) / twoSigma2);
    sum += s.ori * w;
    wsum += w;
  }
  if (wsum > 0) return sum / wsum;
  return oriAt(arr, t);
}

/** Soften a list of Y positions so the stroke does not look jagged. */
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
  const xSpan = Math.abs(pts[pts.length - 1].x - pts[0].x);
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

export function RateGraph({
  faceFound,
  lastBlinkAt,
  alertOri = DEFAULT_ALERT_ORI,
}: RateGraphProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 320, h: 200 });
  // Bumped on every history tick so React redraws the SVG.
  const [frame, setFrame] = useState(0);
  const [blinkFlash, setBlinkFlash] = useState(false);
  const prevBlinkAt = useRef(0);
  const [hover, setHover] = useState<{
    x: number;
    y: number | null;
    bpm: number | null;
    regularity: number | null;
    agoS: number;
  } | null>(null);

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
    // Redraw whenever the 5-minute history adds a new sample.
    return subscribeRateHistory(() => {
      setFrame((n) => (n + 1) % 1_000_000);
    });
  }, []);

  useEffect(() => {
    // Flash the small blink dot when a blink is counted.
    if (!lastBlinkAt || lastBlinkAt === prevBlinkAt.current) return;
    prevBlinkAt.current = lastBlinkAt;
    setBlinkFlash(true);
    const id = window.setTimeout(() => setBlinkFlash(false), 420);
    return () => window.clearTimeout(id);
  }, [lastBlinkAt]);

  const plot = useMemo(() => {
    const { w, h } = size;
    const plotW = Math.max(1, w - PAD.left - PAD.right);
    const plotH = Math.max(1, h - PAD.top - PAD.bottom);
    return { plotW, plotH };
  }, [size]);

  const clientToPlot = useCallback(
    (clientX: number, clientY: number) => {
      const svg = wrapRef.current?.querySelector("svg");
      if (!svg) return null;
      const r = svg.getBoundingClientRect();
      if (r.width <= 0 || r.height <= 0) return null;
      const x = ((clientX - r.left) / r.width) * size.w;
      const y = ((clientY - r.top) / r.height) * size.h;
      return { x, y };
    },
    [size.w, size.h],
  );

  const onPlotMove = (event: MouseEvent<SVGRectElement>) => {
    const pt = clientToPlot(event.clientX, event.clientY);
    if (!pt) {
      setHover(null);
      return;
    }
    const { plotW, plotH } = plot;
    if (
      pt.x < PAD.left ||
      pt.x > PAD.left + plotW ||
      pt.y < PAD.top ||
      pt.y > PAD.top + plotH
    ) {
      setHover(null);
      return;
    }
    const now = performance.now();
    const uFromLeft = (pt.x - PAD.left) / plotW;
    const t = now - uFromLeft * RATE_WINDOW_S * 1000;
    const arr = getRateSamples();
    const sample = nearestSample(arr, t);
    const live = isLiveSample(sample);
    const at = oriAt(arr, t);
    const v =
      at === null ? null : (averagedOri(arr, t, AVG_HALF_S * 1000) ?? at);
    const y =
      v !== null
        ? PAD.top + plotH - (capOriForGraph(v) / Y_MAX) * plotH
        : null;
    setHover({
      x: pt.x,
      y,
      bpm: live ? sample.bpm : null,
      regularity: live ? sample.regularity : null,
      agoS: Math.max(0, (now - t) / 1000),
    });
  };

  const { pathD, nowOri } = useMemo(() => {
    void frame;
    const now = performance.now();
    const arr = getRateSamples();
    const halfMs = AVG_HALF_S * 1000;
    const tStart = now - RATE_WINDOW_S * 1000;

    const { w, h } = size;
    const plotW = Math.max(1, w - PAD.left - PAD.right);
    const plotH = Math.max(1, h - PAD.top - PAD.bottom);

    const uOf = (t: number) =>
      Math.max(0, Math.min(1, (t - tStart) / (RATE_WINDOW_S * 1000)));
    // ORI: now on the left, −5m on the right.
    const xOf = (t: number) => PAD.left + (1 - uOf(t)) * plotW;
    const yOf = (ori: number) =>
      PAD.top + plotH - (capOriForGraph(ori) / Y_MAX) * plotH;

    const segs: { x: number; y: number }[][] = [];

    if (arr.length > 0) {
      const dataStart = Math.max(tStart, arr[0].t);
      const dataEnd = now;
      const spanMs = Math.max(1, dataEnd - dataStart);
      const n = Math.max(
        8,
        Math.min(DRAW_POINTS, Math.ceil(spanMs / 50) + 2),
      );

      // One “run” is a continuous line; a gap (no face) starts a new run.
      let run: { x: number; y: number }[] = [];
      const flush = () => {
        if (run.length > 0) {
          const xs = run.map((p) => p.x);
          const ys = blurYs(
            run.map((p) => p.y),
            GAUSS_RADIUS,
          );
          segs.push(xs.map((x, i) => ({ x, y: ys[i] })));
          run = [];
        }
      };

      for (let i = 0; i < n; i++) {
        const u = n === 1 ? 1 : i / (n - 1);
        const t = dataStart + u * spanMs;
        if (isAbsentAt(arr, t)) {
          flush();
          continue;
        }
        const at = oriAt(arr, t);
        const v = at === null ? null : (averagedOri(arr, t, halfMs) ?? at);
        if (v === null) {
          flush();
          continue;
        }
        run.push({
          x: Math.max(PAD.left, Math.min(PAD.left + plotW, xOf(t))),
          y: yOf(v),
        });
      }
      flush();

      const latest = arr[arr.length - 1];
      const live = getOriEma();
      const liveHead = faceFound && isLiveSample(latest) && live !== null;
      if (liveHead && segs.length > 0) {
        const last = segs[segs.length - 1];
        if (last.length > 0) {
          last[last.length - 1] = {
            x: PAD.left,
            y: yOf(live),
          };
        }
      }
    }

    return {
      pathD: segs.map(smoothPath).filter(Boolean).join(" "),
      nowOri: getOriEma(),
    };
  }, [frame, size, faceFound]);

  const { w, h } = size;
  const plotW = Math.max(1, w - PAD.left - PAD.right);
  const plotH = Math.max(1, h - PAD.top - PAD.bottom);
  const yOf = (ori: number) =>
    PAD.top + plotH - (capOriForGraph(ori) / Y_MAX) * plotH;

  const bandTop = yOf(Y_MAX);
  const bandBot = yOf(GOOD_ORI_MIN);
  const threshold = Number.isFinite(alertOri) ? alertOri : DEFAULT_ALERT_ORI;
  const alertY = yOf(threshold);
  const headX = PAD.left;
  const headY = nowOri !== null ? yOf(nowOri) : null;
  const displayOri = nowOri !== null ? capOriForGraph(nowOri) : null;

  return (
    <div
      className="rate-graph"
      ref={wrapRef}
      aria-label="Ocular Rhythm Index, last 5 minutes. Hover for rate and regularity."
    >
      <div className="rate-graph__chrome" aria-hidden>
        <div className="rate-graph__live rate-graph__live--rate" aria-live="polite">
          <span className="rate-graph__live-value">
            {faceFound && displayOri !== null ? displayOri.toFixed(0) : "—"}
          </span>
          <span className="rate-graph__live-unit">/100</span>
        </div>
        <div className="rate-graph__header-mid">
          <span className="rate-graph__swatch rate-graph__swatch--rate" />
          <span className="rate-graph__legend-item">ORI</span>
          <div
            className={`rate-graph__blink-dot ${blinkFlash ? "is-flash" : ""} ${
              faceFound ? "" : "is-idle"
            }`}
            title="Blink indicator"
          />
        </div>
        <div />
      </div>

      <svg
        className="rate-graph__svg"
        width={w}
        height={h}
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="xMidYMid meet"
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
                className="rate-graph__axis-label rate-graph__axis-label--rate"
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
          className="rate-graph__axis-label rate-graph__axis-label--rate"
        >
          0
        </text>

        <line
          x1={PAD.left}
          y1={alertY}
          x2={PAD.left + plotW}
          y2={alertY}
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

        {faceFound && headY !== null ? (
          <circle cx={headX} cy={headY} r={3} className="rate-graph__head" />
        ) : null}

        <rect
          x={PAD.left}
          y={PAD.top}
          width={plotW}
          height={plotH}
          fill="transparent"
          className="rate-graph__hit"
          onMouseMove={onPlotMove}
          onMouseLeave={() => setHover(null)}
        />

        {hover ? (
          <g className="rate-graph__hover" pointerEvents="none">
            <line
              x1={hover.x}
              y1={PAD.top}
              x2={hover.x}
              y2={PAD.top + plotH}
              className="rate-graph__hover-line"
            />
            {hover.y !== null ? (
              <circle
                cx={hover.x}
                cy={hover.y}
                r={4}
                className="rate-graph__hover-dot"
              />
            ) : null}
          </g>
        ) : null}

        <text
          x={PAD.left}
          y={h - 8}
          className="rate-graph__axis-label rate-graph__axis-label--rate"
          textAnchor="start"
        >
          now
        </text>
        <text
          x={PAD.left + plotW}
          y={h - 8}
          className="rate-graph__axis-label rate-graph__axis-label--rate"
          textAnchor="end"
        >
          −5m
        </text>
      </svg>

      {/* Only show the prompt before any real trail exists — not on brief face loss. */}
      {!faceFound && getRateSamples().length < 8 && (
        <div className="rate-graph__empty">
          Face the camera to start the trace
        </div>
      )}

      {hover ? (
        <div
          className="rate-graph__tip"
          style={{
            left: Math.min(
              Math.max(hover.x + 8, PAD.left),
              size.w - 128,
            ),
            top: PAD.top + 6,
          }}
        >
          <div className="rate-graph__tip-time">
            {hover.agoS < 5
              ? "now"
              : hover.agoS < 60
                ? `−${Math.round(hover.agoS)}s`
                : `−${Math.floor(hover.agoS / 60)}m ${Math.round(hover.agoS % 60)}s`}
          </div>
          <div>
            Rate{" "}
            <strong>
              {hover.bpm !== null ? formatBpm(hover.bpm) : "—"}
            </strong>
            {hover.bpm !== null ? <span> /min</span> : null}
          </div>
          <div>
            Regularity{" "}
            <strong>
              {hover.regularity !== null
                ? Math.round(hover.regularity)
                : "—"}
            </strong>
            {hover.regularity !== null ? <span> /100</span> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
