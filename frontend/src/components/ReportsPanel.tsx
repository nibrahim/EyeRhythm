/**
 * Reports dock: daily 5-min ORI bars, weekly bars, monthly daily bars.
 * Period is chosen by the user; data comes from ori_history.json.
 */

import { useEffect, useState } from "react";
import { fetchReport, fetchReportIndex, type ReportPayload } from "../api";
import { ReportChart } from "./ReportChart";

type Kind = "daily" | "weekly" | "monthly";

function todayISO(): string {
  const d = new Date();
  const z = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}

function monthValue(isoDate: string): string {
  return isoDate.slice(0, 7);
}

export function ReportsPanel() {
  const [kind, setKind] = useState<Kind>("daily");
  const [date, setDate] = useState(todayISO());
  const [report, setReport] = useState<ReportPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchReportIndex()
      .then((idx) => {
        if (!cancelled && idx.today) setDate(idx.today);
      })
      .catch(() => {
        /* keep local today */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    const args =
      kind === "monthly"
        ? {
            kind,
            year: Number(date.slice(0, 4)),
            month: Number(date.slice(5, 7)),
          }
        : { kind, date };
    void fetchReport(args)
      .then((r) => {
        if (!cancelled) setReport(r);
      })
      .catch(() => {
        if (!cancelled) {
          setReport(null);
          setError("Could not load this period.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [kind, date]);

  const periodLabel =
    kind === "daily"
      ? date
      : kind === "weekly" && report?.week_start
        ? `${report.week_start} – ${report.week_end}`
        : monthValue(date);

  return (
    <div className="reports">
      <div className="reports__kinds" role="tablist" aria-label="Report period">
        {(["daily", "weekly", "monthly"] as const).map((k) => (
          <button
            key={k}
            type="button"
            className={`reports__kind${kind === k ? " is-active" : ""}`}
            onClick={() => setKind(k)}
          >
            {k[0].toUpperCase() + k.slice(1)}
          </button>
        ))}
      </div>

      <label className="reports__date">
        <span>{kind === "monthly" ? "Month" : kind === "weekly" ? "Week of" : "Day"}</span>
        {kind === "monthly" ? (
          <input
            type="month"
            value={monthValue(date)}
            onChange={(e) => {
              const v = e.target.value;
              if (v) setDate(`${v}-01`);
            }}
          />
        ) : (
          <input
            type="date"
            value={date}
            onChange={(e) => {
              if (e.target.value) setDate(e.target.value);
            }}
          />
        )}
      </label>

      <p className="reports__caption">
        {kind === "daily" && "5-minute mean ORI across 24 hours"}
        {kind === "weekly" && "Daily mean ORI, Monday–Sunday"}
        {kind === "monthly" && "Daily mean ORI for the month"}
        {periodLabel ? ` · ${periodLabel}` : ""}
      </p>

      {error ? <p className="settings__help">{error}</p> : null}
      {report ? <ReportChart report={report} /> : null}
    </div>
  );
}
