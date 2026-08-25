/**
 * Talking to the local Python server
 * ==================================
 *
 * The dashboard never talks to the internet. All of these helpers call
 * `http://127.0.0.1:8742` (or whatever port this window was opened on):
 *
 * * REST  — one-shot questions (“save this avatar”, “flip Beep”)
 * * WebSocket — a live pipe of blink numbers (~10 times a second)
 *
 * If a call fails, the UI stays on its last known values rather than crashing.
 */
import type { EngineState, ToggleName } from "./types";

/** Settings remembered from last launch (avatar, window size, switches). */
export interface Preferences {
  avatar: string;
  compact: boolean;
  window_width: number;
  window_height: number;
  beep: boolean;
  alert: boolean;
  ontop: boolean;
  /** Last splash self-check: comfortable | mild | moderate | marked | decline */
  eye_comfort?: string;
  dock?: boolean;
  ori_threshold?: number;
  writing_angle_deg?: number;
  close_delta?: number;
}

export interface LiveSettings {
  ori_threshold: number;
  writing_angle_deg: number;
  close_delta: number;
}

export interface AuditEntry {
  at: string;
  setting: string;
  from: number | string;
  to: number | string;
  label?: string;
}

export interface ReportPoint {
  date?: string;
  label?: string;
  t?: string;
  i?: number;
  ori: number | null;
  screen_s: number;
  blinks: number;
}

export interface ReportPayload {
  kind: "daily" | "weekly" | "monthly";
  ori_threshold: number;
  date?: string;
  week_start?: string;
  week_end?: string;
  year?: number;
  month?: number;
  bin_minutes?: number;
  points?: ReportPoint[];
  days?: ReportPoint[];
  summary: {
    mean_ori: number | null;
    screen_s: number;
    blinks: number;
    days_with_data: number;
  };
}

/** One famous quote shown on the Information card. */
export interface QuoteItem {
  text: string;
  author: string;
}

/** Bundle the Practice screen uses: quotes + how often to rotate them. */
export interface QuotesPayload {
  count: number;
  interval_seconds: number;
  practice_duration_seconds: number;
  quotes: QuoteItem[];
}

/** Load the quote list from disk via the local API. */
export async function fetchQuotes(): Promise<QuotesPayload> {
  const res = await fetch("/api/quotes", { cache: "no-store" });
  if (!res.ok) throw new Error("quotes fetch failed");
  const data = await res.json();
  // Normalize legacy string quotes if any slip through.
  const quotes: QuoteItem[] = Array.isArray(data.quotes)
    ? data.quotes.map((q: unknown) => {
        if (typeof q === "string") return { text: q, author: "Unknown" };
        const obj = q as { text?: string; author?: string };
        return {
          text: String(obj.text ?? ""),
          author: String(obj.author ?? "Unknown"),
        };
      }).filter((q: QuoteItem) => q.text.trim().length > 0)
    : [];
  return { ...data, quotes };
}


function wsBase(): string {
  // Same host as the page; use the encrypted `wss` only if the page is https.
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}`;
}

/** Last-session avatar, compact mode, window size, and durable toggles. */
export async function fetchPreferences(): Promise<Preferences> {
  const res = await fetch("/api/preferences", { cache: "no-store" });
  if (!res.ok) throw new Error("preferences fetch failed");
  return res.json();
}

/** Merge a few changed settings (e.g. `{ avatar: "lumen" }`) onto disk. */
export async function savePreferences(
  patch: Partial<Preferences>,
): Promise<Preferences> {
  const res = await fetch("/api/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error("preferences save failed");
  return res.json();
}

/**
 * Open a live numbers pipe. Calls `onState` every time a snapshot arrives.
 *
 * If the engine restarts, this reconnects automatically (with a growing wait)
 * until the caller unsubscribes by running the returned cleanup function.
 */
export function connectStatsSocket(
  onState: (s: EngineState) => void,
  onStatus?: (connected: boolean) => void,
): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  // First retry is quick; later retries slow down so we do not hammer the CPU.
  let retryMs = 400;

  const connect = () => {
    if (closed) return;
    ws = new WebSocket(`${wsBase()}/ws/stats`);
    ws.onopen = () => {
      retryMs = 400;
      onStatus?.(true);
    };
    ws.onmessage = (ev) => {
      try {
        onState(JSON.parse(ev.data) as EngineState);
      } catch {
        /* ignore bad frames */
      }
    };
    ws.onclose = () => {
      onStatus?.(false);
      if (!closed) {
        window.setTimeout(connect, retryMs);
        retryMs = Math.min(4000, retryMs * 1.5);
      }
    };
    ws.onerror = () => {
      ws?.close();
    };
  };

  connect();

  return () => {
    closed = true;
    ws?.close();
  };
}

export async function fetchSettings(): Promise<LiveSettings> {
  const res = await fetch("/api/settings", { cache: "no-store" });
  if (!res.ok) throw new Error("settings fetch failed");
  return res.json();
}

export async function saveSettings(
  patch: Partial<LiveSettings>,
): Promise<LiveSettings> {
  const res = await fetch("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error("settings save failed");
  return res.json();
}

export async function fetchAudit(limit = 24): Promise<AuditEntry[]> {
  const res = await fetch(`/api/audit?limit=${limit}`, { cache: "no-store" });
  if (!res.ok) throw new Error("audit fetch failed");
  const data = await res.json();
  return Array.isArray(data.entries) ? data.entries : [];
}

export async function fetchReportIndex(): Promise<{
  today: string;
  days: string[];
  ori_threshold: number;
}> {
  const res = await fetch("/api/reports?kind=index", { cache: "no-store" });
  if (!res.ok) throw new Error("reports index failed");
  return res.json();
}

export async function fetchReport(params: {
  kind: "daily" | "weekly" | "monthly";
  date?: string;
  year?: number;
  month?: number;
}): Promise<ReportPayload> {
  const q = new URLSearchParams({ kind: params.kind });
  if (params.date) q.set("date", params.date);
  if (params.year != null) q.set("year", String(params.year));
  if (params.month != null) q.set("month", String(params.month));
  const res = await fetch(`/api/reports?${q.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error("report fetch failed");
  return res.json();
}

/** Turn Beep / Alert / On top / Practice on or off (omit value = flip). */
export async function setToggle(
  name: ToggleName,
  value?: boolean,
): Promise<Record<string, boolean>> {
  const res = await fetch(`/api/toggles/${name}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(value === undefined ? {} : { value }),
  });
  if (!res.ok) {
    throw new Error(`toggle ${name} failed`);
  }
  return res.json();
}

/** Tell the engine to start/stop encoding camera JPEGs for the Lens avatar. */
export async function setPreviewEnabled(enabled: boolean): Promise<void> {
  await fetch(`/api/preview/${enabled ? "enable" : "disable"}`, {
    method: "POST",
  });
}

/**
 * Ask for a fresh camera still every ~120 ms (Lens avatar).
 *
 * Returns a stop function: turn off encoding and free the last image.
 */
export function startPreviewPolling(
  onFrame: (url: string | null) => void,
  intervalMs = 120,
): () => void {
  let active = true;
  let objectUrl: string | null = null;
  let timer: number | undefined;

  const tick = async () => {
    if (!active) return;
    try {
      const res = await fetch(`/api/preview?t=${Date.now()}`, {
        cache: "no-store",
      });
      if (res.status === 200) {
        const blob = await res.blob();
        // Drop the previous image URL so the browser can free that memory.
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = URL.createObjectURL(blob);
        onFrame(objectUrl);
      }
    } catch {
      /* transient */
    }
    if (active) {
      timer = window.setTimeout(tick, intervalMs);
    }
  };

  void setPreviewEnabled(true).then(tick);

  return () => {
    active = false;
    if (timer !== undefined) window.clearTimeout(timer);
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    void setPreviewEnabled(false);
  };
}
