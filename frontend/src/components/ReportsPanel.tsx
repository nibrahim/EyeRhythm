/**
 * Reports dock: daily 5-min ORI bars, weekly bars, monthly daily bars.
 * Period is chosen by the user; data comes from ori_history.json.
 */

import { useEffect, useState } from "react";
import { fetchReport, fetchReportIndex, type ReportPayload } from "../api";
import { ReportChart } from "./ReportChart";
import {
  ReportPeriodPicker,
  todayISO,
  type ReportKind,
} from "./ReportPeriodPicker";

export function ReportsPanel() {
  const [kind, setKind] = useState<ReportKind>("daily");
  const [date, setDate] = useState(todayISO());
  const [today, setToday] = useState(todayISO());
  const [daysWithData, setDaysWithData] = useState<string[]>([]);
  const [report, setReport] = useState<ReportPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchReportIndex()
      .then((idx) => {
        if (cancelled) return;
        if (idx.today) {
          setToday(idx.today);
          setDate(idx.today);
        }
        if (Array.isArray(idx.days)) setDaysWithData(idx.days);
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

      <ReportPeriodPicker
        kind={kind}
        date={date}
        today={today}
        daysWithData={daysWithData}
        onChange={setDate}
      />

      <p className="reports__caption">
        {kind === "daily" && "5-minute mean ORI across 24 hours"}
        {kind === "weekly" && "Daily mean ORI, Monday–Sunday"}
        {kind === "monthly" && "Daily mean ORI for the month"}
        {" · Green dotted line is the trained-eye target (75)"}
      </p>

      {error ? <p className="settings__help">{error}</p> : null}
      {report ? <ReportChart report={report} /> : null}
    </div>
  );
}
