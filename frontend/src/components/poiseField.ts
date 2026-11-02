/**
 * Top-down bowl for Poise.
 *
 * The picture is a glowing blue dial. Up is the top, down is the bottom,
 * and the person's right is on the right. Eight spokes divide it into
 * 45° sectors. The rim is a 90° tilt. A sector fills from the center
 * toward the rim with an orange gradient; a full radius is five hours.
 * The ball is the only moving marker. It rolls with the face.
 */

export const RIM_DEG = 90;
export const BIN_COUNT = 8;
/** Yaw and pitch scales used only to pick a sector. They match face_motion.py. */
const YAW_EDGE = 50;
const PITCH_EDGE = 40;

export interface BowlAim {
  /** Unit-disk coordinate. +x is right. +y is up, the top of the dial. */
  x: number;
  y: number;
  /** Combined tilt in degrees, clamped to the rim. */
  deg: number;
}

/**
 * Where the ball sits. 90° reaches the rim. The angle matches
 * direction_bin, so the ball stays inside the sector that is filling.
 */
export function bowlAim(lr: number, up: number, down: number): BowlAim {
  const nx = lr / YAW_EDGE;
  const ny = (down - up) / PITCH_EDGE;
  const ang = Math.atan2(-ny, nx);
  const deg = Math.min(RIM_DEG, Math.hypot(lr, up - down));
  const reach = deg / RIM_DEG;
  return {
    x: Math.cos(ang) * reach,
    y: Math.sin(ang) * reach,
    deg,
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

function sectorSpan(index: number): [number, number] {
  const width = (2 * Math.PI) / BIN_COUNT;
  const center = index * width;
  return [center - width / 2, center + width / 2];
}

/**
 * Draw the dial into a canvas context already scaled to CSS pixels.
 * `values` are fractions of five hours, one per sector. `aim` is the
 * live face direction, or null when the face is gone.
 */
export function drawBowl(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  values: ArrayLike<number>,
  aim: BowlAim | null,
): void {
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#070b12";
  ctx.fillRect(0, 0, w, h);
  if (w < 2 || h < 2) return;

  const cx = w * 0.5;
  const cy = h * 0.5;
  const radius = Math.min(w, h) * 0.36;

  const at = (u: number, ang: number): [number, number] => [
    cx + Math.cos(ang) * radius * u,
    cy - Math.sin(ang) * radius * u,
  ];

  const disk = ctx.createRadialGradient(cx, cy, radius * 0.08, cx, cy, radius);
  disk.addColorStop(0, "#102033");
  disk.addColorStop(0.72, "#0a1422");
  disk.addColorStop(1, "#07101c");
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.fillStyle = disk;
  ctx.fill();

  for (let i = 0; i < BIN_COUNT; i++) {
    const v = Math.max(0, Math.min(1, values[i] || 0));
    if (v <= 0.004) continue;
    const outer = radius * v;
    const [a0, a1] = sectorSpan(i);
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(outer, 1));
    grad.addColorStop(0, "rgba(255, 196, 110, 0.18)");
    grad.addColorStop(0.5, "rgba(255, 146, 40, 0.62)");
    grad.addColorStop(1, "rgba(255, 102, 12, 0.92)");
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    const steps = 14;
    for (let s = 0; s <= steps; s++) {
      const ang = a0 + ((a1 - a0) * s) / steps;
      ctx.lineTo(cx + Math.cos(ang) * outer, cy - Math.sin(ang) * outer);
    }
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();
  }

  ctx.lineCap = "round";
  ctx.lineWidth = 1;
  ctx.strokeStyle = "rgba(120, 186, 235, 0.38)";
  for (let k = 1; k <= 6; k++) {
    ctx.beginPath();
    ctx.arc(cx, cy, radius * (k / 6), 0, Math.PI * 2);
    ctx.stroke();
  }

  ctx.strokeStyle = "rgba(96, 176, 235, 0.72)";
  ctx.lineWidth = 1.15;
  for (let i = 0; i < BIN_COUNT; i++) {
    const ang = (i * 2 * Math.PI) / BIN_COUNT;
    const [x1, y1] = at(1, ang);
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(x1, y1);
    ctx.stroke();
  }

  ctx.save();
  ctx.shadowColor = "rgba(80, 176, 255, 0.95)";
  ctx.shadowBlur = 16;
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.lineWidth = 3;
  ctx.strokeStyle = "rgba(186, 224, 255, 0.95)";
  ctx.stroke();
  ctx.shadowBlur = 28;
  ctx.lineWidth = 8;
  ctx.strokeStyle = "rgba(70, 160, 255, 0.35)";
  ctx.stroke();
  ctx.restore();

  ctx.font = "600 13px ui-sans-serif, system-ui, sans-serif";
  ctx.fillStyle = "rgba(232, 238, 246, 0.92)";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const labelR = radius + 16;
  const place = (text: string, x: number, y: number) => {
    ctx.fillText(text, Math.max(16, Math.min(w - 16, x)), Math.max(12, Math.min(h - 12, y)));
  };
  place("R", cx + labelR, cy);
  place("L", cx - labelR, cy);
  place("up", cx, cy - labelR);
  place("down", cx, cy + labelR);

  ctx.font = "600 11px ui-sans-serif, system-ui, sans-serif";
  ctx.fillStyle = "rgba(232, 196, 130, 0.92)";
  ctx.textAlign = "left";
  const markAng = -0.62;
  for (const deg of [30, 60, 90]) {
    const u = deg / RIM_DEG;
    const x = cx + Math.cos(markAng) * radius * u + 6;
    const y = cy - Math.sin(markAng) * radius * u;
    ctx.fillText(`${deg}°`, x, y);
  }

  const travel = radius - 7;
  const bx = cx + (aim ? aim.x * travel : 0);
  const by = cy - (aim ? aim.y * travel : 0);
  const haloR = radius * 0.34;
  const halo = ctx.createRadialGradient(bx, by, 0, bx, by, haloR);
  halo.addColorStop(0, "rgba(255, 214, 140, 0.95)");
  halo.addColorStop(0.18, "rgba(255, 168, 64, 0.55)");
  halo.addColorStop(0.45, "rgba(255, 140, 40, 0.18)");
  halo.addColorStop(1, "rgba(255, 120, 20, 0)");
  ctx.beginPath();
  ctx.arc(bx, by, haloR, 0, Math.PI * 2);
  ctx.fillStyle = halo;
  ctx.fill();

  const core = radius * 0.045;
  const hx = bx - (aim ? aim.x : 0.35) * core * 0.8;
  const hy = by + (aim ? aim.y : 0.35) * core * 0.8;
  const sphere = ctx.createRadialGradient(hx, hy, core * 0.15, bx, by, core);
  sphere.addColorStop(0, "#fffef8");
  sphere.addColorStop(0.55, "#fff4dc");
  sphere.addColorStop(1, "#f0c27a");
  ctx.beginPath();
  ctx.arc(bx, by, core, 0, Math.PI * 2);
  ctx.fillStyle = sphere;
  ctx.fill();
}
