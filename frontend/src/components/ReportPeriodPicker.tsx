/**
 * Period stepper + in-app calendar for Reports.
 *
 * Native <input type="date|month"> pickers do not open in the desktop
 * webview, so this is buttons only: previous / next, a readable label
 * that opens a small calendar, and Today.
 */

import { useEffect, useMemo, useRef, useState } from "react";

export type ReportKind = "daily" | "weekly" | "monthly";

const WEEKDAYS = ["M", "T", "W", "T", "F", "S", "S"] as const;
const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function parseISO(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

function toISO(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function addDays(iso: string, n: number): string {
  const d = parseISO(iso);
  d.setDate(d.getDate() + n);
  return toISO(d);
}

function addMonths(iso: string, n: number): string {
  const d = parseISO(iso);
  d.setMonth(d.getMonth() + n);
  return toISO(d);
}

function mondayISO(iso: string): string {
  const d = parseISO(iso);
  const offset = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - offset);
  return toISO(d);
}

function clampISO(iso: string, min: string, max: string): string {
  if (iso < min) return min;
  if (iso > max) return max;
  return iso;
}

function monthGrid(year: number, month: number): { iso: string; inMonth: boolean }[] {
  const first = new Date(year, month, 1);
  const startOffset = (first.getDay() + 6) % 7;
  const start = new Date(year, month, 1 - startOffset);
  const cells: { iso: string; inMonth: boolean }[] = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
    cells.push({ iso: toISO(d), inMonth: d.getMonth() === month });
  }
  return cells;
}

function formatDaily(iso: string): string {
  return parseISO(iso).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatWeekly(iso: string): string {
  const start = parseISO(mondayISO(iso));
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  const d1 = start.getDate();
  const d2 = end.getDate();
  const m1 = start.toLocaleDateString(undefined, { month: "short" });
  const m2 = end.toLocaleDateString(undefined, { month: "short" });
  const y1 = start.getFullYear();
  const y2 = end.getFullYear();
  if (start.getMonth() === end.getMonth()) return `${d1}–${d2} ${m2} ${y2}`;
  if (y1 === y2) return `${d1} ${m1} – ${d2} ${m2} ${y2}`;
  return `${d1} ${m1} ${y1} – ${d2} ${m2} ${y2}`;
}

function formatMonthly(iso: string): string {
  return parseISO(iso).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
}

function stepISO(kind: ReportKind, iso: string, dir: -1 | 1): string {
  if (kind === "daily") return addDays(iso, dir);
  if (kind === "weekly") return addDays(iso, dir * 7);
  return addMonths(iso, dir);
}

interface Props {
  kind: ReportKind;
  date: string;
  today: string;
  daysWithData?: string[];
  onChange: (iso: string) => void;
}

export function ReportPeriodPicker({
  kind,
  date,
  today,
  daysWithData,
  onChange,
}: Props) {
  const min = addDays(today, -400);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const selected = parseISO(date);
  const [viewYear, setViewYear] = useState(selected.getFullYear());
  const [viewMonth, setViewMonth] = useState(selected.getMonth());

  useEffect(() => {
    setOpen(false);
  }, [kind]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const dataDays = useMemo(() => new Set(daysWithData ?? []), [daysWithData]);
  const cells = useMemo(
    () => monthGrid(viewYear, viewMonth),
    [viewYear, viewMonth],
  );
  const selectedWeek = mondayISO(date);
  const todayWeek = mondayISO(today);
  const todayMonth = today.slice(0, 7);

  const label =
    kind === "daily"
      ? formatDaily(date)
      : kind === "weekly"
        ? formatWeekly(date)
        : formatMonthly(date);

  const atLatest =
    kind === "daily"
      ? date >= today
      : kind === "weekly"
        ? selectedWeek >= todayWeek
        : date.slice(0, 7) >= todayMonth;

  const atEarliest =
    kind === "daily"
      ? date <= min
      : kind === "weekly"
        ? mondayISO(date) <= mondayISO(min)
        : date.slice(0, 7) <= min.slice(0, 7);

  const atNow =
    kind === "daily"
      ? date === today
      : kind === "weekly"
        ? selectedWeek === todayWeek
        : date.slice(0, 7) === todayMonth;

  const shift = (dir: -1 | 1) => {
    const next = clampISO(stepISO(kind, date, dir), min, today);
    onChange(next);
  };

  const openPicker = () => {
    const d = parseISO(date);
    setViewYear(d.getFullYear());
    setViewMonth(d.getMonth());
    setOpen((v) => !v);
  };

  const pickDay = (iso: string) => {
    if (iso > today) return;
    onChange(clampISO(iso, min, today));
    setOpen(false);
  };

  const pickMonth = (year: number, month: number) => {
    const iso = `${year}-${pad(month + 1)}-01`;
    if (iso.slice(0, 7) > todayMonth) return;
    onChange(clampISO(iso, min, today));
    setOpen(false);
  };

  const shiftView = (dir: -1 | 1) => {
    if (kind === "monthly") {
      setViewYear((y) => y + dir);
      return;
    }
    const d = new Date(viewYear, viewMonth + dir, 1);
    setViewYear(d.getFullYear());
    setViewMonth(d.getMonth());
  };

  const viewTitle =
    kind === "monthly"
      ? String(viewYear)
      : new Date(viewYear, viewMonth, 1).toLocaleDateString(undefined, {
          month: "long",
          year: "numeric",
        });

  const stepBack =
    kind === "daily" ? "Previous day" : kind === "weekly" ? "Previous week" : "Previous month";
  const stepFwd =
    kind === "daily" ? "Next day" : kind === "weekly" ? "Next week" : "Next month";

  return (
    <div className="reports__period" ref={wrapRef}>
      <div className="reports__period-row">
        <div className="reports__period-nav">
          <button
            type="button"
            className="reports__period-step"
            aria-label={stepBack}
            disabled={atEarliest}
            onClick={() => shift(-1)}
          >
            ‹
          </button>
          <button
            type="button"
            className={`reports__period-label${open ? " is-open" : ""}`}
            aria-expanded={open}
            aria-haspopup="dialog"
            onClick={openPicker}
          >
            {label}
          </button>
          <button
            type="button"
            className="reports__period-step"
            aria-label={stepFwd}
            disabled={atLatest}
            onClick={() => shift(1)}
          >
            ›
          </button>
        </div>
        <button
          type="button"
          className="reports__period-now"
          disabled={atNow}
          onClick={() => {
            onChange(today);
            setOpen(false);
          }}
        >
          Today
        </button>
      </div>

      {open ? (
        <div className="reports__picker" role="dialog" aria-label="Choose period">
          <div className="reports__picker-head">
            <button
              type="button"
              className="reports__period-step"
              aria-label="Previous"
              onClick={() => shiftView(-1)}
            >
              ‹
            </button>
            <div className="reports__picker-title">{viewTitle}</div>
            <button
              type="button"
              className="reports__period-step"
              aria-label="Next"
              onClick={() => shiftView(1)}
            >
              ›
            </button>
          </div>

          {kind === "monthly" ? (
            <div className="reports__months">
              {MONTHS.map((name, month) => {
                const key = `${viewYear}-${pad(month + 1)}`;
                const future = key > todayMonth;
                const active = date.slice(0, 7) === key;
                const isNow = todayMonth === key;
                return (
                  <button
                    key={name}
                    type="button"
                    className={`reports__month${active ? " is-selected" : ""}${
                      isNow ? " is-today" : ""
                    }`}
                    disabled={future}
                    onClick={() => pickMonth(viewYear, month)}
                  >
                    {name}
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="reports__cal">
              {WEEKDAYS.map((w, i) => (
                <div key={`${w}-${i}`} className="reports__cal-dow">
                  {w}
                </div>
              ))}
              {cells.map((cell) => {
                const future = cell.iso > today;
                const selectedDay = kind === "daily" && cell.iso === date;
                const inWeek =
                  kind === "weekly" && mondayISO(cell.iso) === selectedWeek;
                const isNow = cell.iso === today;
                const hasData = dataDays.has(cell.iso);
                return (
                  <button
                    key={cell.iso}
                    type="button"
                    className={`reports__cal-day${cell.inMonth ? "" : " is-muted"}${
                      selectedDay || inWeek ? " is-selected" : ""
                    }${isNow ? " is-today" : ""}${hasData ? " has-data" : ""}`}
                    disabled={future}
                    onClick={() => pickDay(cell.iso)}
                  >
                    {parseISO(cell.iso).getDate()}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
