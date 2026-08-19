/**
 * Session-wide ORI history for the Trace graph.
 *
 * Lives at module scope so samples keep accumulating for the last 5 minutes
 * even when the user switches away from Trace to another avatar, and even
 * when the window is minimized (uses setInterval, not rAF — rAF freezes
 * when the webview is hidden).
 *
 * Smoothing pipeline (ECG-style glide):
 *   engine ORI → triple EMA → slew limit → stored samples
 * After a gap the filters seed to the new ORI so the trail does not climb
 * from 0 (that would look like an alert-zone dip).
 */

export interface RateSample {
  t: number;
  /** Null while no-face / looking down / ORI unavailable — a gap, not 0. */
  ori: number | null;
  /** False = do not plot this instant. */
  present: boolean;
}

/** Visible + retained time window (seconds). */
export const RATE_WINDOW_S = 300;
/** Dense samples make the scroll feel continuous (~12.5 Hz). */
const SAMPLE_MS = 80;
const HISTORY_PAD_S = 12;
const MAX_SAMPLES =
  Math.ceil(((RATE_WINDOW_S + HISTORY_PAD_S) * 1000) / SAMPLE_MS) + 40;
/**
 * Triple EMA alphas (per ~80ms sample step). Smaller = silkier.
 * Cascade kills the stair-steps from discrete engine updates.
 */
const EMA1 = 0.18;
const EMA2 = 0.22;
const EMA3 = 0.28;
/** Hard limit on how fast the plotted ORI may change (points per second). */
const MAX_SLEW_ORI_PER_S = 16;
const Y_CAP = 100;
/** How often UI subscribers are notified (ms). */
const NOTIFY_MS = 50;
/**
 * Max lag to catch up after background throttle / long sleep (ms).
 * Beyond this we just resume from "now" (older window is pruned anyway).
 */
const MAX_CATCHUP_MS = 5000;

function capGraph(ori: number): number {
  // Never plot below 0 or above 100 (ORI’s published range).
  return Math.min(Y_CAP, Math.max(0, ori));
}

const samples: RateSample[] = [];
let ema1 = 0;
let ema2 = 0;
let ema3 = 0;
let smooth = 0;
let targetOri: number | null = null;
/** On-screen (face found and not looking down off-screen). */
let targetPresent = false;
/** Filters hold a real ORI — false after a gap until the next live value. */
let filtersLive = false;
let lastSampleAt = 0;
let lastNotifyAt = 0;
let running = false;
let intervalId: ReturnType<typeof setInterval> | null = null;
const listeners = new Set<() => void>();

function nowMs(): number {
  // performance.now() keeps advancing while the window is minimized;
  // Date.now() would also work but mixes poorly with existing rAF code.
  return performance.now();
}

function prune(now: number): void {
  const cutoff = now - (RATE_WINDOW_S + HISTORY_PAD_S) * 1000;
  while (samples.length > 0 && samples[0].t < cutoff) samples.shift();
  if (samples.length > MAX_SAMPLES) {
    samples.splice(0, samples.length - MAX_SAMPLES);
  }
}

function seedFilters(ori: number): void {
  ema1 = ema2 = ema3 = smooth = ori;
  filtersLive = true;
}

function gapHead(t: number): RateSample {
  return { t, ori: null, present: false };
}

/** Advance filters by one fixed sample step and push a sample. */
function advanceOneStep(sampleT: number, dtS: number): void {
  if (!targetPresent || targetOri === null) {
    samples.push(gapHead(sampleT));
    lastSampleAt = sampleT;
    filtersLive = false;
    return;
  }

  if (!filtersLive) {
    seedFilters(targetOri);
  } else {
    ema1 += (targetOri - ema1) * EMA1;
    ema2 += (ema1 - ema2) * EMA2;
    ema3 += (ema2 - ema3) * EMA3;

    const maxStep = MAX_SLEW_ORI_PER_S * dtS;
    const delta = ema3 - smooth;
    if (delta > maxStep) smooth += maxStep;
    else if (delta < -maxStep) smooth -= maxStep;
    else smooth = ema3;
  }

  samples.push({
    t: sampleT,
    ori: smooth,
    present: true,
  });
  lastSampleAt = sampleT;
}

function notify(): void {
  for (const cb of listeners) {
    try {
      cb();
    } catch {
      /* subscriber error must not stop the sampler */
    }
  }
}

/**
 * Interval tick: keep sampling even when the window is minimized.
 * If the timer was throttled, catch up a few steps so the trail stays continuous.
 */
function tick(): void {
  const now = nowMs();

  if (lastSampleAt <= 0) {
    // First sample of the session — start the trail immediately.
    advanceOneStep(now, SAMPLE_MS / 1000);
    prune(now);
    lastNotifyAt = now;
    notify();
    return;
  }

  const lag = now - lastSampleAt;
  if (lag < SAMPLE_MS * 0.5) {
    // Too soon (spurious double-fire); just refresh the head.
    if (samples.length > 0) {
      samples[samples.length - 1] =
        targetPresent && targetOri !== null
          ? { t: now, ori: smooth, present: true }
          : gapHead(now);
    }
    return;
  }

  // Catch up missed steps (background throttle), capped so a long sleep
  // does not burn a huge loop — the 5-minute prune handles the rest.
  const catchUp = Math.min(lag, MAX_CATCHUP_MS);
  const steps = Math.max(1, Math.round(catchUp / SAMPLE_MS));
  const dtS = SAMPLE_MS / 1000;
  // Place samples ending at `now` so the head stays on the right edge.
  const startT = now - (steps - 1) * SAMPLE_MS;
  for (let i = 0; i < steps; i++) {
    advanceOneStep(startT + i * SAMPLE_MS, dtS);
  }
  // Pin the latest sample exactly to now.
  if (samples.length > 0) {
    samples[samples.length - 1] =
      targetPresent && targetOri !== null
        ? { t: now, ori: smooth, present: true }
        : gapHead(now);
    lastSampleAt = now;
  }

  prune(now);

  if (now - lastNotifyAt >= NOTIFY_MS) {
    lastNotifyAt = now;
    notify();
  }
}

/**
 * Feed the latest engine ORI. Safe to call every websocket tick.
 * When ``present`` is false (no-face or looking down off-screen) the
 * trail records a gap — time still advances, the line cuts immediately.
 * ``ori === null`` (warming up / no usable rate) is also a gap.
 */
export function setRateHistoryInput(
  ori: number | null,
  present = true,
): void {
  const nextPresent = Boolean(present);
  const nextOri =
    ori !== null && Number.isFinite(ori) ? capGraph(ori) : null;
  const dropped = targetPresent && !nextPresent;
  targetPresent = nextPresent;
  targetOri = targetPresent ? nextOri : null;
  ensureRateHistoryRunning();
  // Cut the trail on this tick — do not wait for the next 80ms sample.
  if (dropped) {
    const t = nowMs();
    samples.push(gapHead(t));
    lastSampleAt = t;
    filtersLive = false;
    notify();
  }
}

/** Start the background sampler (idempotent). Keeps running for the session. */
export function ensureRateHistoryRunning(): void {
  if (running) return;
  running = true;
  lastSampleAt = 0;
  // Seed an immediate gap so Trace has a trail from t=0.
  const t0 = nowMs();
  samples.push(gapHead(t0));
  lastSampleAt = t0;
  // setInterval survives minimize/hide; rAF does not.
  intervalId = setInterval(tick, SAMPLE_MS);
  // Run one tick soon so the first non-zero engine values are not delayed.
  tick();
}

export function getRateSamples(): readonly RateSample[] {
  return samples;
}

/** Latest smoothed ORI, or null while away / warming up. */
export function getOriEma(): number | null {
  if (!filtersLive || !targetPresent || targetOri === null) return null;
  return smooth;
}

/** Subscribe to sample ticks (for Trace redraw). Returns unsubscribe. */
export function subscribeRateHistory(cb: () => void): () => void {
  listeners.add(cb);
  // Ensure sampling even if only the graph subscribed (e.g. hot reload).
  ensureRateHistoryRunning();
  return () => {
    listeners.delete(cb);
  };
}

export function capOriForGraph(ori: number): number {
  return capGraph(ori);
}

/** Test / hot-reload helper — not used in production UI. */
export function _resetRateHistoryForTests(): void {
  if (intervalId !== null) {
    clearInterval(intervalId);
    intervalId = null;
  }
  running = false;
  samples.length = 0;
  ema1 = ema2 = ema3 = smooth = 0;
  targetOri = null;
  targetPresent = false;
  filtersLive = false;
  lastSampleAt = lastNotifyAt = 0;
  listeners.clear();
}
