/**
 * Balance dial for Poise.
 *
 * Up is the top, down is the bottom, and the person's right is on the
 * right. Twelve 30° directions fan out from a "straight ahead" hub. Each
 * direction is a stack of rounded tiles colored by how much it was used
 * compared with the most used direction: red where the head barely went,
 * green where it went most. Tiles light from the hub outward as a
 * direction warms up. Every day starts all red. The weakest direction
 * pulses with an arrow on the bezel, the hub gauges overall balance, and
 * a glowing ball with a short trail rolls with the face.
 */

export const BIN_COUNT = 12;
/** Yaw and pitch scales used only to pick a sector. They match face_motion.py. */
const YAW_EDGE = 50;
const PITCH_EDGE = 40;
/** Inside this reach the face is straight ahead. Matches DEAD_REACH. */
const DEAD_REACH = 0.3;
/** Fractions below this count as no data yet (about one second of five hours). */
const EMPTY = 1 / 18000;
/** Tiles per direction, hub to rim. */
const TILES = 4;

const SECTOR_NAMES = [
  "right",
  "right, up",
  "up, right",
  "up",
  "up, left",
  "left, up",
  "left",
  "left, down",
  "down, left",
  "down",
  "down, right",
  "right, down",
];

export interface BowlAim {
  /** Unit-disk coordinate. +x is right. +y is up, the top of the dial. */
  x: number;
  y: number;
  /** Sector being looked at, or null inside the straight-ahead hub. */
  sector: number | null;
}

export interface Balance {
  /** 0..1 per sector, relative to the most used sector. All 0 before any data. */
  heat: Float32Array;
  /** 0..1 mean heat across all twelve sectors. */
  score: number;
  most: number | null;
  least: number | null;
}

type Rgb = [number, number, number];

function sectorIndex(angle: number): number {
  const width = (2 * Math.PI) / BIN_COUNT;
  const i = Math.floor((angle + width / 2) / width) % BIN_COUNT;
  return i < 0 ? i + BIN_COUNT : i;
}

export function sectorName(index: number): string {
  return SECTOR_NAMES[index] ?? "";
}

/**
 * Where the ball sits. Same math as direction_bin, so the ball enters the
 * ring exactly when a direction starts to count.
 */
export function bowlAim(lr: number, up: number, down: number): BowlAim {
  let nx = Math.max(-1, Math.min(1, lr / YAW_EDGE));
  let ny = Math.max(-1, Math.min(1, (down - up) / PITCH_EDGE));
  const reach = Math.hypot(nx, ny);
  if (reach > 1) {
    nx /= reach;
    ny /= reach;
  }
  return {
    x: nx,
    y: -ny,
    sector: reach < DEAD_REACH ? null : sectorIndex(Math.atan2(-ny, nx)),
  };
}

/** Little-endian uint16 → 0..1. Length must be BIN_COUNT. */
export function decodeBins(b64: string): Float32Array | null {
  if (!b64) return null;
  const bin = atob(b64);
  if (bin.length !== BIN_COUNT * 2) return null;
  const out = new Float32Array(BIN_COUNT);
  for (let i = 0; i < BIN_COUNT; i++) {
    const lo = bin.charCodeAt(i * 2);
    const hi = bin.charCodeAt(i * 2 + 1);
    out[i] = (lo + hi * 256) / 65535;
  }
  return out;
}

/**
 * Heat per direction plus the strongest and weakest. Ties for the weakest
 * go to the direction whose neighbors are also least used, so the arrow
 * points into the middle of a neglected region.
 */
export function balanceOf(values: ArrayLike<number>): Balance {
  const heat = new Float32Array(BIN_COUNT);
  let max = 0;
  let total = 0;
  for (let i = 0; i < BIN_COUNT; i++) {
    const v = Math.max(0, values[i] || 0);
    max = Math.max(max, v);
    total += v;
  }
  if (max < EMPTY) return { heat, score: 0, most: null, least: null };

  let most = 0;
  let least = 0;
  let leastKey = Infinity;
  for (let i = 0; i < BIN_COUNT; i++) {
    const v = Math.max(0, values[i] || 0);
    heat[i] = v / max;
    if (v > (values[most] || 0)) most = i;
    const prev = Math.max(0, values[(i + BIN_COUNT - 1) % BIN_COUNT] || 0);
    const next = Math.max(0, values[(i + 1) % BIN_COUNT] || 0);
    const key = v + 0.25 * (prev + next);
    if (key < leastKey) {
      leastKey = key;
      least = i;
    }
  }
  // Average heat: 100% only when every direction is as green as the best one.
  return { heat, score: total / max / BIN_COUNT, most, least };
}

/** Red → amber → green. */
function heatRgb(t: number): Rgb {
  const red: Rgb = [255, 77, 94];
  const amber: Rgb = [255, 184, 64];
  const green: Rgb = [40, 230, 150];
  const [a, b, u] = t < 0.5 ? [red, amber, t * 2] : [amber, green, (t - 0.5) * 2];
  return [
    Math.round(a[0] + (b[0] - a[0]) * u),
    Math.round(a[1] + (b[1] - a[1]) * u),
    Math.round(a[2] + (b[2] - a[2]) * u),
  ];
}

function rgba([r, g, b]: Rgb, a: number): string {
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

/**
 * Annular tile path for direction `index` between radii r0 and r1, inset
 * by `pad` pixels on every side. Stroke it with lineWidth 2 * pad and a
 * round join to get rounded corners back out to the full size.
 */
function tilePath(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  r0: number,
  r1: number,
  index: number,
  pad: number,
): void {
  const width = (2 * Math.PI) / BIN_COUNT;
  const mid = index * width;
  const inR = r0 + pad;
  const outR = Math.max(inR + 0.5, r1 - pad);
  // Canvas angles run clockwise, so the dial angle is negated.
  const lo = -(mid + width / 2);
  const hi = -(mid - width / 2);
  ctx.beginPath();
  ctx.arc(cx, cy, outR, lo + pad / outR, hi - pad / outR);
  ctx.arc(cx, cy, inR, hi - pad / inR, lo + pad / inR, true);
  ctx.closePath();
}

/**
 * Draw the dial into a canvas context already scaled to CSS pixels.
 * `values` are fractions of five hours, one per sector. `trail` is the
 * recent live aims, newest last; empty when the face is gone. `now`
 * drives the pulse on the weakest direction.
 */
export function drawBowl(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  values: ArrayLike<number>,
  trail: readonly BowlAim[],
  now: number,
): void {
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#070b12";
  ctx.fillRect(0, 0, w, h);
  if (w < 2 || h < 2) return;

  const cx = w * 0.5;
  const cy = h * 0.5;
  const radius = Math.min(w, h) * 0.37;
  const inner = radius * DEAD_REACH;
  const band = (radius - inner) / TILES;
  const width = (2 * Math.PI) / BIN_COUNT;
  const { heat, score, least } = balanceOf(values);
  const aim = trail.length ? trail[trail.length - 1] : null;
  const pulse = 0.5 + 0.5 * Math.sin(now / 320);

  // Soft colored aura: each direction tints the space behind it.
  for (let i = 0; i < BIN_COUNT; i++) {
    const ang = i * width;
    const ax = cx + Math.cos(ang) * radius * 0.75;
    const ay = cy - Math.sin(ang) * radius * 0.75;
    const aura = ctx.createRadialGradient(ax, ay, 0, ax, ay, radius * 0.75);
    aura.addColorStop(0, rgba(heatRgb(heat[i]), 0.08));
    aura.addColorStop(1, rgba(heatRgb(heat[i]), 0));
    ctx.fillStyle = aura;
    ctx.fillRect(0, 0, w, h);
  }

  // Bezel: a thin ring with a tick every 10° and a longer one every 30°.
  const bezel = radius + 7;
  ctx.lineCap = "round";
  for (let k = 0; k < 36; k++) {
    const ang = (k * Math.PI) / 18 + width / 2;
    const major = k % 3 === 0;
    const len = major ? 4 : 2;
    const ux = Math.cos(ang);
    const uy = -Math.sin(ang);
    ctx.beginPath();
    ctx.moveTo(cx + ux * (bezel - len / 2), cy + uy * (bezel - len / 2));
    ctx.lineTo(cx + ux * (bezel + len / 2), cy + uy * (bezel + len / 2));
    ctx.lineWidth = major ? 1.2 : 0.8;
    ctx.strokeStyle = major ? "rgba(170, 200, 235, 0.45)" : "rgba(170, 200, 235, 0.2)";
    ctx.stroke();
  }

  ctx.lineJoin = "round";
  const pad = 1.6;
  for (let i = 0; i < BIN_COUNT; i++) {
    const t = heat[i];
    const rgb = heatRgb(t);
    for (let k = 0; k < TILES; k++) {
      const r0 = inner + band * k;
      const lit = t >= (k + 0.5) / TILES;
      const fill = lit ? rgba(rgb, 0.92 - 0.1 * k) : rgba(rgb, 0.16 + 0.04 * (TILES - k));
      ctx.save();
      if (lit && t > 0.5) {
        ctx.shadowColor = rgba(rgb, 0.85);
        ctx.shadowBlur = 4 + 10 * (t - 0.5);
      }
      tilePath(ctx, cx, cy, r0, r0 + band, i, pad);
      ctx.fillStyle = fill;
      ctx.strokeStyle = fill;
      ctx.lineWidth = pad * 1.2;
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }
  }

  if (aim && aim.sector !== null) {
    ctx.save();
    tilePath(ctx, cx, cy, inner, radius, aim.sector, 0.5);
    ctx.shadowColor = "rgba(255, 255, 255, 0.9)";
    ctx.shadowBlur = 8;
    ctx.lineWidth = 1.4;
    ctx.strokeStyle = "rgba(255, 255, 255, 0.8)";
    ctx.stroke();
    ctx.restore();
  }

  if (least !== null) {
    ctx.save();
    tilePath(ctx, cx, cy, inner, radius, least, 0.5);
    ctx.setLineDash([3, 3]);
    ctx.lineDashOffset = -now / 60;
    ctx.lineWidth = 1.3;
    ctx.strokeStyle = `rgba(255, 210, 215, ${0.4 + 0.5 * pulse})`;
    ctx.stroke();
    ctx.restore();

    const ang = least * width;
    const ux = Math.cos(ang);
    const uy = -Math.sin(ang);
    const r0 = bezel + 2 + 3 * pulse;
    const tip = 8;
    const half = 5;
    const bx = cx + ux * r0;
    const by = cy + uy * r0;
    ctx.save();
    ctx.shadowColor = "rgba(255, 77, 94, 0.9)";
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.moveTo(bx + ux * tip, by + uy * tip);
    ctx.lineTo(bx - uy * half, by + ux * half);
    ctx.lineTo(bx + uy * half, by - ux * half);
    ctx.closePath();
    ctx.fillStyle = `rgba(255, 96, 110, ${0.65 + 0.35 * pulse})`;
    ctx.fill();
    ctx.restore();
  }

  // Hub: glass disc with a ring gauge for the balance score.
  const hubR = inner - 3;
  const glass = ctx.createRadialGradient(cx - hubR * 0.3, cy - hubR * 0.4, 0, cx, cy, hubR);
  glass.addColorStop(0, "#1a2c44");
  glass.addColorStop(1, "#0a1220");
  ctx.beginPath();
  ctx.arc(cx, cy, hubR, 0, Math.PI * 2);
  ctx.fillStyle = glass;
  ctx.fill();
  const gaugeR = hubR - 2;
  ctx.beginPath();
  ctx.arc(cx, cy, gaugeR, 0, Math.PI * 2);
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
  ctx.stroke();
  const scoreRgb = heatRgb(score);
  if (score > 0.005) {
    ctx.save();
    ctx.shadowColor = rgba(scoreRgb, 0.9);
    ctx.shadowBlur = 6;
    ctx.beginPath();
    ctx.arc(cx, cy, gaugeR, -Math.PI / 2, -Math.PI / 2 + score * Math.PI * 2);
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.strokeStyle = rgba(scoreRgb, 1);
    ctx.stroke();
    ctx.restore();
  }

  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const hubFont = Math.max(10, Math.min(15, hubR * 0.62));
  ctx.font = `700 ${Math.round(hubFont)}px ui-sans-serif, system-ui, sans-serif`;
  ctx.fillStyle = rgba(scoreRgb, 1);
  ctx.fillText(`${Math.round(score * 100)}%`, cx, cy - hubFont * 0.12);
  ctx.font = `600 ${Math.max(6, Math.round(hubFont * 0.42))}px ui-sans-serif, system-ui, sans-serif`;
  ctx.fillStyle = "rgba(200, 214, 232, 0.6)";
  ctx.fillText("BALANCE", cx, cy + hubFont * 0.6);

  ctx.font = "700 9px ui-sans-serif, system-ui, sans-serif";
  ctx.fillStyle = "rgba(200, 214, 232, 0.7)";
  const labelR = bezel + 14;
  const place = (text: string, x: number, y: number) => {
    ctx.fillText(text, Math.max(14, Math.min(w - 14, x)), Math.max(8, Math.min(h - 8, y)));
  };
  place("R", cx + labelR, cy);
  place("L", cx - labelR, cy);
  place("UP", cx, cy - labelR);
  place("DOWN", cx, cy + labelR);

  if (!aim) return;
  const at = (a: BowlAim): [number, number] => [cx + a.x * radius, cy - a.y * radius];

  // Comet trail: older points are thinner and fainter.
  ctx.lineCap = "round";
  for (let i = 1; i < trail.length; i++) {
    const age = i / trail.length;
    const [x0, y0] = at(trail[i - 1]);
    const [x1, y1] = at(trail[i]);
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.lineWidth = 0.6 + 3 * age;
    ctx.strokeStyle = `rgba(190, 230, 255, ${0.5 * age})`;
    ctx.stroke();
  }

  const [bx, by] = at(aim);
  const glowR = radius * 0.2;
  const glow = ctx.createRadialGradient(bx, by, 0, bx, by, glowR);
  glow.addColorStop(0, "rgba(255, 255, 255, 0.5)");
  glow.addColorStop(0.4, "rgba(150, 215, 255, 0.15)");
  glow.addColorStop(1, "rgba(150, 215, 255, 0)");
  ctx.beginPath();
  ctx.arc(bx, by, glowR, 0, Math.PI * 2);
  ctx.fillStyle = glow;
  ctx.fill();
  const core = Math.max(3, radius * 0.05);
  ctx.beginPath();
  ctx.arc(bx, by, core, 0, Math.PI * 2);
  ctx.fillStyle = "#ffffff";
  ctx.fill();
  ctx.lineWidth = 1.2;
  ctx.strokeStyle = "rgba(7, 11, 18, 0.8)";
  ctx.stroke();
}
