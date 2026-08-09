/**
 * Practice ball path — every throw starts from screen center.
 *
 * Cycle (each leg = one beep interval; disappear + beep at progress = 1):
 *   0 Center → Top-left
 *   1 Center → Bottom-left
 *   2 Center → Bottom-right
 *   3 Center → Top-right
 *   4 Center — 2 full spirals (short radius) back to center
 *
 * Beep timing: PracticeCoach beeps at the end of each interval. Opacity and
 * arrival are keyed to progress → 1 so they hit on the same instant.
 */

export interface Point {
  x: number;
  y: number;
}

export interface BallSample {
  point: Point;
  /** 0…1 draw opacity (0 = ball + string hidden). */
  opacity: number;
  segment: number;
  progress: number;
}

export const CENTER: Point = { x: 0.5, y: 0.5 };

export const PRACTICE_CYCLE_STEPS = 5;

export const DEFAULT_EDGE_MARGIN = 0.02;

/** Soft loft of each throw (normalized screen units at mid-flight). */
const THROW_LOFT = 0.05;

/** Two full revolutions while the spiral returns to center. */
const SPIRAL_TURNS = 2.0;

/**
 * Peak spiral radius as a fraction of the distance from center to the edge
 * (after margin). Smaller = shorter string during the spiral.
 */
const SPIRAL_RADIUS_FRAC = 0.38;

/**
 * Fade-out window at the end of each interval (fraction of interval).
 * Completes at progress = 1.0 so disappear matches the beep.
 */
const FADE_OUT_FRAC = 0.06;

/** Brief fade-in when leaving center. */
const FADE_IN_FRAC = 0.06;

function clamp01(t: number): number {
  return t < 0 ? 0 : t > 1 ? 1 : t;
}

function smootherstep(t: number): number {
  const u = clamp01(t);
  return u * u * u * (u * (u * 6 - 15) + 10);
}

/**
 * Motion ease: soft leave + soft land, but still arrives at the target
 * only at t = 1 (no early “already there” hang before the beep).
 */
function throwEase(t: number): number {
  return smootherstep(t);
}

function corners(mx: number, my: number): {
  topLeft: Point;
  bottomLeft: Point;
  bottomRight: Point;
  topRight: Point;
} {
  return {
    topLeft: { x: mx, y: my },
    bottomLeft: { x: mx, y: 1 - my },
    bottomRight: { x: 1 - mx, y: 1 - my },
    topRight: { x: 1 - mx, y: my },
  };
}

/** Ballistic throw from A → B with loft away from screen center. */
function throwArc(a: Point, b: Point, t: number): Point {
  const u = throwEase(t);
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  let px = -dy / len;
  let py = dx / len;
  const midX = a.x + dx * 0.5;
  const midY = a.y + dy * 0.5;
  if (px * (midX - 0.5) + py * (midY - 0.5) < 0) {
    px = -px;
    py = -py;
  }
  const loft = THROW_LOFT * 4 * u * (1 - u);
  return {
    x: a.x + dx * u + px * loft,
    y: a.y + dy * u + py * loft,
  };
}

/**
 * Opacity timeline aligned to the beep (progress = 1):
 *   fade in → fully solid → quick dissolve finishing at t = 1.
 * Ball + string share this value.
 */
function throwOpacity(t: number): number {
  const u = clamp01(t);
  if (u < FADE_IN_FRAC) {
    return smootherstep(u / FADE_IN_FRAC);
  }
  const fadeStart = 1 - FADE_OUT_FRAC;
  if (u < fadeStart) {
    return 1;
  }
  // Exactly 0 at u = 1 (beep moment).
  return 1 - smootherstep((u - fadeStart) / FADE_OUT_FRAC);
}

/**
 * Spiral from center: 2 full turns, short radius, back to center at t = 1.
 * r = 0 at start and end; peaks mid-interval.
 */
function spiralFromCenter(rMax: number, t: number): Point {
  const u = clamp01(t);
  const s = smootherstep(u);
  // Out and back to center after two revolutions.
  const r = rMax * Math.sin(Math.PI * s);
  const angle = -Math.PI / 2 + SPIRAL_TURNS * Math.PI * 2 * s;
  return {
    x: CENTER.x + r * Math.cos(angle),
    y: CENTER.y + r * Math.sin(angle),
  };
}

/**
 * Ball state for continuous elapsed time from practice start.
 * Every segment begins at CENTER; disappear completes at progress = 1 (beep).
 */
export function ballPositionAt(
  elapsedS: number,
  intervalS: number,
  marginX: number = DEFAULT_EDGE_MARGIN,
  marginY: number = DEFAULT_EDGE_MARGIN,
): BallSample {
  const iv = Math.max(0.05, intervalS);
  const t = Math.max(0, elapsedS);
  const totalSteps = Math.floor(t / iv);
  const segment = totalSteps % PRACTICE_CYCLE_STEPS;
  // Cap just below 1 so we never spill into the next segment early;
  // when t lands exactly on a boundary, floor advances — correct for beep.
  const rawProgress = (t - totalSteps * iv) / iv;
  const progress = Math.min(1, Math.max(0, rawProgress));

  const mx = Math.min(0.45, Math.max(0.005, marginX));
  const my = Math.min(0.45, Math.max(0.005, marginY));
  const c = corners(mx, my);
  const rMax = Math.min(0.5 - mx, 0.5 - my) * SPIRAL_RADIUS_FRAC;

  let point: Point;
  switch (segment) {
    case 0:
      point = throwArc(CENTER, c.topLeft, progress);
      break;
    case 1:
      point = throwArc(CENTER, c.bottomLeft, progress);
      break;
    case 2:
      point = throwArc(CENTER, c.bottomRight, progress);
      break;
    case 3:
      point = throwArc(CENTER, c.topRight, progress);
      break;
    case 4:
    default:
      point = spiralFromCenter(rMax, progress);
      break;
  }

  const opacity = throwOpacity(progress);

  point = {
    x: Math.min(1 - mx * 0.1, Math.max(mx * 0.1, point.x)),
    y: Math.min(1 - my * 0.1, Math.max(my * 0.1, point.y)),
  };

  return { point, opacity, segment, progress };
}
