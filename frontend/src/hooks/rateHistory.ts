/**
 * Session-wide continuous-rate history for the Trace graph.
 *
 * Lives at module scope so samples keep accumulating for the last 5 minutes
 * even when the user switches away from Trace to another avatar.
 *
 * Smoothing pipeline (ECG-style glide):
 *   engine bpm → triple EMA → slew limit → stored samples
 * Never snaps to the first non-zero reading (that caused a jump to 30).
 */

export interface RateSample {
  t: number;
  bpm: number;
}

/** Visible + retained time window (seconds). */
export const RATE_WINDOW_S = 300;
/** Dense samples make the scroll feel continuous. */
const SAMPLE_MS = 80;
const HISTORY_PAD_S = 12;
const MAX_SAMPLES =
  Math.ceil(((RATE_WINDOW_S + HISTORY_PAD_S) * 1000) / SAMPLE_MS) + 40;
/**
 * Triple EMA alphas (per ~16ms frame). Smaller = silkier, slower response.
 * Cascade kills the stair-steps from discrete engine updates.
 */
const EMA1 = 0.05;
const EMA2 = 0.08;
const EMA3 = 0.12;
/** Hard limit on how fast the plotted value may change (bpm per second). */
const MAX_SLEW_BPM_PER_S = 5.5;
const Y_CAP = 30;

function capGraph(bpm: number): number {
  return Math.min(Y_CAP, Math.max(0, bpm));
}

const samples: RateSample[] = [];
let ema1 = 0;
let ema2 = 0;
let ema3 = 0;
let smooth = 0;
let targetBpm = 0;
let lastSampleAt = 0;
let lastTickAt = 0;
let running = false;
let lastNotify = 0;
const listeners = new Set<() => void>();

function prune(now: number): void {
  const cutoff = now - (RATE_WINDOW_S + HISTORY_PAD_S) * 1000;
  while (samples.length > 0 && samples[0].t < cutoff) samples.shift();
  if (samples.length > MAX_SAMPLES) {
    samples.splice(0, samples.length - MAX_SAMPLES);
  }
}

function tick(ts: number): void {
  const now = performance.now();
  const dt = lastTickAt > 0 ? Math.min(0.05, (now - lastTickAt) / 1000) : 1 / 60;
  lastTickAt = now;

  // Always ease — never snap to the first engine value (avoids a jump to 30).
  ema1 += (targetBpm - ema1) * EMA1;
  ema2 += (ema1 - ema2) * EMA2;
  ema3 += (ema2 - ema3) * EMA3;

  // Slew-rate limit so big jumps become gentle slopes.
  const maxStep = MAX_SLEW_BPM_PER_S * dt;
  const delta = ema3 - smooth;
  if (delta > maxStep) smooth += maxStep;
  else if (delta < -maxStep) smooth -= maxStep;
  else smooth = ema3;

  // Keep a tiny floor at zero so we don't store noise.
  if (smooth < 0.02 && targetBpm < 0.02) smooth = 0;

  if (now - lastSampleAt >= SAMPLE_MS) {
    lastSampleAt = now;
    if (
      samples.length === 0 ||
      now - samples[samples.length - 1].t >= SAMPLE_MS * 0.55
    ) {
      samples.push({ t: now, bpm: smooth });
    } else {
      samples[samples.length - 1] = { t: now, bpm: smooth };
    }
    prune(now);
  } else if (samples.length > 0) {
    samples[samples.length - 1] = { t: now, bpm: smooth };
  } else {
    samples.push({ t: now, bpm: smooth });
  }

  if (ts - lastNotify >= 33) {
    lastNotify = ts;
    for (const cb of listeners) cb();
  }

  requestAnimationFrame(tick);
}

/** Feed the latest engine reading. Safe to call every websocket tick. */
export function setRateHistoryInput(
  continuousBpm: number,
  faceFound: boolean,
): void {
  targetBpm = faceFound ? capGraph(Math.max(0, continuousBpm)) : 0;
}

/** Start the background sampler (idempotent). Keeps running for the session. */
export function ensureRateHistoryRunning(): void {
  if (running) return;
  running = true;
  lastTickAt = 0;
  requestAnimationFrame(tick);
}

export function getRateSamples(): readonly RateSample[] {
  return samples;
}

export function getRateEma(): number {
  return smooth;
}

/** Subscribe to sample ticks (for Trace redraw). Returns unsubscribe. */
export function subscribeRateHistory(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export function capRateForGraph(bpm: number): number {
  return capGraph(bpm);
}
