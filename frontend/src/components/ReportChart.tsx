/**
 * Settings-dock report charts: daily / weekly / monthly bars.
 * ORI uses the Trace scale (0–100, red dotted threshold, green target 75).
 * Screen time uses minutes (daily 5-min slots) or hours (week / month).
 */

import { useEffect, useMemo, useRef, useState } from "react";
import type { ReportPayload } from "../api";
import { formatScreenTime } from "../utils/format";

const PAD = { top: 18, right: 10, bottom: 22, left: 28 };
const ORI_MAX = 100;
/** Target ORI after the user has trained their blink muscles. */
const TARGET_ORI = 75;
const DAILY_BIN_S = 5 * 60;
const HOUR_S = 3600;
const NICE_HOURS = [1, 2, 3, 4, 6, 8, 10, 12, 14, 16, 18, 20, 24];

export type ReportMetric = "ori" | "screen";

interface Props {
  report: ReportPayload;
  metric?: ReportMetric;
}

function yOf(value: number, yMax: number, plotH: number): number {
  const v = Math.max(0, Math.min(yMax, value));
  return PAD.top + plotH - (v / yMax) * plotH;
}

function barClass(kind: ReportPayload["kind"], metric: ReportMetric): string {
  const extra =
    kind === "daily"
      ? " report-chart__bar--daily"
      : kind === "monthly"
        ? " report-chart__bar--monthly"
        : "";
  const screen = metric === "screen" ? " report-chart__bar--screen" : "";
  return `report-chart__bar${extra}${screen}`;
}

function niceScreenMax(maxS: number, kind: ReportPayload["kind"]): number {
  if (kind === "daily") return DAILY_BIN_S;
  if (maxS <= 0) return 8 * HOUR_S;
  const hours = maxS / HOUR_S;
  for (const h of NICE_HOURS) {
    if (hours <= h) return h * HOUR_S;
  }
  return Math.ceil(hours) * HOUR_S;
}

function axisTimeLabel(seconds: number, kind: ReportPayload["kind"]): string {
  if (kind === "daily") {
    const m = seconds / 60;
    if (m <= 0) return "0";
    return Number.isInteger(m) ? `${m}m` : `${m}m`;
  }
  const h = seconds / HOUR_S;
  if (h <= 0) return "0";
  if (h < 1) return `${Math.round(h * 60)}m`;
  return Number.isInteger(h) ? `${h}h` : `${h}h`;
}

export function ReportChart({ report, metric = "ori" }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(340);
  const h = 168;

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const apply = (width: number) => {
      const next = Math.max(200, Math.round(width));
      setW((prev) => (prev === next ? prev : next));
    };
    apply(el.getBoundingClientRect().width);
    const ro = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect;
      if (r && r.width > 0) apply(r.width);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const plotW = w - PAD.left - PAD.right;
  const plotH = h - PAD.top - PAD.bottom;
  const threshold = report.ori_threshold ?? 50;
  const alertY = yOf(threshold, ORI_MAX, plotH);
  const targetY = yOf(TARGET_ORI, ORI_MAX, plotH);

  const series = useMemo(() => {
    if (report.kind === "daily") return report.points ?? [];
    return report.days ?? [];
  }, [report]);

  const n = Math.max(1, series.length);
  const gap = report.kind === "daily" ? 0.12 : 0.38;
  const bw = (plotW / n) * (1 - gap);
  const screenMax = Math.max(0, ...series.map((p) => p.screen_s || 0));
  const yMax = metric === "screen" ? niceScreenMax(screenMax, report.kind) : ORI_MAX;

  const xTicks = useMemo(() => {
    if (report.kind === "daily") {
      return [0, 6, 12, 18, 24].map((hr) => ({
        x: PAD.left + (hr / 24) * plotW,
        label: `${String(hr).padStart(2, "0")}:00`,
      }));
    }
    if (report.kind === "weekly") {
      return series.map((p, i) => ({
        x: PAD.left + ((i + 0.5) / n) * plotW,
        label: p.label ?? "",
      }));
    }
    const out: { x: number; label: string }[] = [];
    series.forEach((p, i) => {
      const day = Number(p.label);
      if (day === 1 || day % 5 === 0) {
        out.push({
          x: PAD.left + ((i + 0.5) / n) * plotW,
          label: String(day),
        });
      }
    });
    return out;
  }, [n, plotW, report.kind, series]);

  const yTicks = useMemo(() => {
    if (metric !== "screen") return [];
    if (report.kind === "daily") {
      return [0, DAILY_BIN_S].map((value) => ({
        value,
        y: yOf(value, yMax, plotH),
        label: axisTimeLabel(value, report.kind),
      }));
    }
    return [0, yMax / 2, yMax].map((value) => ({
      value,
      y: yOf(value, yMax, plotH),
      label: axisTimeLabel(value, report.kind),
    }));
  }, [metric, plotH, report.kind, yMax]);

  const summary = report.summary;
  const mean = summary.mean_ori;
  const screenDays = series.filter((p) => (p.screen_s || 0) > 0).length;
  const dailyAvg =
    report.kind === "daily" || screenDays <= 0
      ? null
      : summary.screen_s / screenDays;
  const empty =
    metric === "ori"
      ? series.every((p) => p.ori == null)
      : series.every((p) => !(p.screen_s > 0));

  return (
    <div
      className={`report-chart${metric === "screen" ? " is-screen" : ""}`}
      ref={wrapRef}
    >
      <svg
        className="report-chart__svg"
        width={w}
        height={h}
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="xMidYMid meet"
        aria-label={
          metric === "screen"
            ? `${report.kind} screen time`
            : `${report.kind} Ocular Rhythm Index`
        }
      >
        {metric === "ori" ? (
          <>
            <line
              x1={PAD.left}
              y1={targetY}
              x2={PAD.left + plotW}
              y2={targetY}
              className="report-chart__target-line"
            />
            <text
              x={PAD.left - 4}
              y={targetY + 3}
              textAnchor="end"
              className="report-chart__target-label"
            >
              {TARGET_ORI}
            </text>
            <text
              x={PAD.left + plotW - 2}
              y={targetY - 4}
              textAnchor="end"
              className="report-chart__target-label"
            >
              target
            </text>
            <line
              x1={PAD.left}
              y1={alertY}
              x2={PAD.left + plotW}
              y2={alertY}
              className="rate-graph__low-line"
            />
            {Math.abs(threshold - TARGET_ORI) >= 6 ? (
              <text
                x={PAD.left - 4}
                y={alertY + 3}
                textAnchor="end"
                className="rate-graph__axis-label"
              >
                {Math.round(threshold)}
              </text>
            ) : null}
          </>
        ) : (
          yTicks.map((t) =>
            t.value <= 0 ? null : (
              <g key={t.value}>
                <line
                  x1={PAD.left}
                  y1={t.y}
                  x2={PAD.left + plotW}
                  y2={t.y}
                  className="report-chart__grid"
                />
                <text
                  x={PAD.left - 4}
                  y={t.y + 3}
                  textAnchor="end"
                  className="rate-graph__axis-label"
                >
                  {t.label}
                </text>
              </g>
            ),
          )
        )}
        {series.map((p, i) => {
          const value = metric === "ori" ? p.ori : p.screen_s;
          if (value == null) return null;
          if (metric === "screen" && value <= 0) return null;
          const x = PAD.left + ((i + 0.5) / n) * plotW - bw / 2;
          const y = yOf(value, yMax, plotH);
          const bh = PAD.top + plotH - y;
          return (
            <rect
              key={p.date ?? p.t ?? i}
              x={x}
              y={y}
              width={bw}
              height={Math.max(metric === "screen" ? 1 : 0, bh)}
              rx={report.kind === "daily" ? 0.6 : 3}
              className={barClass(report.kind, metric)}
            />
          );
        })}
        <line
          x1={PAD.left}
          y1={PAD.top + plotH}
          x2={PAD.left + plotW}
          y2={PAD.top + plotH}
          className="rate-graph__axis"
        />
        {xTicks.map((t) => (
          <text
            key={t.label + t.x}
            x={t.x}
            y={h - 6}
            textAnchor="middle"
            className="rate-graph__axis-label"
          >
            {t.label}
          </text>
        ))}
      </svg>
      {empty ? (
        <div className="report-chart__empty">
          {metric === "screen"
            ? "No screen time for this period"
            : "No on-screen ORI for this period"}
        </div>
      ) : null}
      {metric === "ori" ? (
        <dl className="report-chart__stats report-chart__stats--2">
          <div>
            <dt>Mean ORI</dt>
            <dd>{mean == null ? "—" : mean.toFixed(0)}</dd>
          </div>
          <div>
            <dt>Blinks</dt>
            <dd>{summary.blinks}</dd>
          </div>
        </dl>
      ) : (
        <dl
          className={`report-chart__stats${
            report.kind === "daily" ? " report-chart__stats--2" : ""
          }`}
        >
          <div>
            <dt>Total</dt>
            <dd>{formatScreenTime(summary.screen_s)}</dd>
          </div>
          {report.kind === "daily" ? (
            <div>
              <dt>Peak 5 min</dt>
              <dd>{formatScreenTime(screenMax)}</dd>
            </div>
          ) : (
            <>
              <div>
                <dt>Daily avg</dt>
                <dd>{dailyAvg == null ? "—" : formatScreenTime(dailyAvg)}</dd>
              </div>
              <div>
                <dt>Days</dt>
                <dd>{screenDays}</dd>
              </div>
            </>
          )}
        </dl>
      )}
    </div>
  );
}
