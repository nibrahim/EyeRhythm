/**
 * Settings-dock report charts: daily line (5-min), weekly bars, monthly line.
 * Same visual language as Trace (ORI 0–100, red dotted threshold).
 */

import { useMemo } from "react";
import type { ReportPayload } from "../api";

const PAD = { top: 18, right: 10, bottom: 22, left: 28 };
const Y_MAX = 100;

interface Props {
  report: ReportPayload;
}

function yOf(ori: number, plotH: number): number {
  return PAD.top + plotH - (Math.max(0, Math.min(Y_MAX, ori)) / Y_MAX) * plotH;
}

function screenLabel(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  if (h <= 0) return `${m}m`;
  const rem = m % 60;
  return rem ? `${h}h ${rem}m` : `${h}h`;
}

export function ReportChart({ report }: Props) {
  const w = 340;
  const h = 168;
  const plotW = w - PAD.left - PAD.right;
  const plotH = h - PAD.top - PAD.bottom;
  const threshold = report.ori_threshold ?? 50;
  const alertY = yOf(threshold, plotH);

  const series = useMemo(() => {
    if (report.kind === "daily") return report.points ?? [];
    return report.days ?? [];
  }, [report]);

  const n = Math.max(1, series.length);

  const path = useMemo(() => {
    if (report.kind === "weekly") return "";
    const segs: string[] = [];
    let d = "";
    series.forEach((p, i) => {
      const x = PAD.left + (i / Math.max(1, n - 1)) * plotW;
      if (p.ori == null || !Number.isFinite(p.ori)) {
        if (d) segs.push(d);
        d = "";
        return;
      }
      const y = yOf(p.ori, plotH);
      d += d ? ` L ${x.toFixed(1)} ${y.toFixed(1)}` : `M ${x.toFixed(1)} ${y.toFixed(1)}`;
    });
    if (d) segs.push(d);
    return segs.join(" ");
  }, [n, plotH, plotW, report.kind, series]);

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
          x: PAD.left + (i / Math.max(1, n - 1)) * plotW,
          label: String(day),
        });
      }
    });
    return out;
  }, [n, plotW, report.kind, series]);

  const summary = report.summary;
  const mean = summary.mean_ori;

  return (
    <div className="report-chart">
      <svg
        className="report-chart__svg"
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        aria-label={`${report.kind} Ocular Rhythm Index`}
      >
        <line
          x1={PAD.left}
          y1={alertY}
          x2={PAD.left + plotW}
          y2={alertY}
          className="rate-graph__low-line"
        />
        <text
          x={PAD.left - 4}
          y={alertY + 3}
          textAnchor="end"
          className="rate-graph__axis-label"
        >
          {Math.round(threshold)}
        </text>
        {report.kind === "weekly"
          ? series.map((p, i) => {
              if (p.ori == null) return null;
              const bw = (plotW / n) * 0.62;
              const x = PAD.left + ((i + 0.5) / n) * plotW - bw / 2;
              const y = yOf(p.ori, plotH);
              const bh = PAD.top + plotH - y;
              return (
                <rect
                  key={p.date ?? i}
                  x={x}
                  y={y}
                  width={bw}
                  height={Math.max(0, bh)}
                  rx={3}
                  className="report-chart__bar"
                />
              );
            })
          : path
            ? (
                <path
                  d={path}
                  className="rate-graph__line rate-graph__line--rate"
                />
              )
            : null}
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
      {series.every((p) => p.ori == null) ? (
        <div className="report-chart__empty">No on-screen ORI for this period</div>
      ) : null}
      <dl className="report-chart__stats">
        <div>
          <dt>Mean ORI</dt>
          <dd>{mean == null ? "—" : mean.toFixed(0)}</dd>
        </div>
        <div>
          <dt>Screen</dt>
          <dd>{screenLabel(summary.screen_s)}</dd>
        </div>
        <div>
          <dt>Blinks</dt>
          <dd>{summary.blinks}</dd>
        </div>
      </dl>
    </div>
  );
}
