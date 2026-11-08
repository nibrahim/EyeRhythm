/**
 * Face-mesh helpers for Poise.
 *
 * Triangles come from MediaPipe's edge list, so their stored winding is
 * arbitrary. `orientTriangles` makes every front face point the same way
 * as the nose (toward +z, the camera).
 */

import { FACE_TRIANGLES } from "./faceTriangles";

export { FACE_TRIANGLES };

type Tri = [number, number, number];

function edgeKey(a: number, b: number): string {
  return a < b ? `${a}_${b}` : `${b}_${a}`;
}

function normalZ(pos: Float32Array, t: Tri): number {
  const a = t[0] * 3;
  const b = t[1] * 3;
  const c = t[2] * 3;
  const ax = pos[b] - pos[a];
  const ay = pos[b + 1] - pos[a + 1];
  const bx = pos[c] - pos[a];
  const by = pos[c + 1] - pos[a + 1];
  return ax * by - ay * bx;
}

function flip(t: Tri): void {
  const x = t[1];
  t[1] = t[2];
  t[2] = x;
}

/** Make triangle normals agree with a nose-outward seed, across shared edges. */
export function orientTriangles(pos: Float32Array, raw: Uint16Array): Uint16Array {
  const tris: Tri[] = [];
  for (let i = 0; i < raw.length; i += 3) {
    tris.push([raw[i], raw[i + 1], raw[i + 2]]);
  }
  const edgeMap = new Map<string, number[]>();
  tris.forEach((t, i) => {
    const edges: [number, number][] = [
      [t[0], t[1]],
      [t[1], t[2]],
      [t[2], t[0]],
    ];
    for (const [a, b] of edges) {
      const k = edgeKey(a, b);
      const list = edgeMap.get(k);
      if (list) list.push(i);
      else edgeMap.set(k, [i]);
    }
  });

  let seed = 0;
  let best = -1;
  for (let i = 0; i < tris.length; i++) {
    const t = tris[i];
    if (t[0] === 1 || t[1] === 1 || t[2] === 1) {
      const area = Math.abs(normalZ(pos, t));
      if (area > best) {
        best = area;
        seed = i;
      }
    }
  }
  if (normalZ(pos, tris[seed]) < 0) flip(tris[seed]);

  const oriented = new Array<boolean>(tris.length).fill(false);
  oriented[seed] = true;
  const stack = [seed];
  while (stack.length) {
    const i = stack.pop() as number;
    const t = tris[i];
    const edges: [number, number][] = [
      [t[0], t[1]],
      [t[1], t[2]],
      [t[2], t[0]],
    ];
    for (const [a, b] of edges) {
      const neighbors = edgeMap.get(edgeKey(a, b));
      if (!neighbors) continue;
      for (const j of neighbors) {
        if (oriented[j]) continue;
        const n = tris[j];
        const same =
          (n[0] === a && n[1] === b) ||
          (n[1] === a && n[2] === b) ||
          (n[2] === a && n[0] === b);
        if (same) flip(n);
        oriented[j] = true;
        stack.push(j);
      }
    }
  }
  for (let i = 0; i < tris.length; i++) {
    if (!oriented[i] && normalZ(pos, tris[i]) < 0) flip(tris[i]);
  }

  const out = new Uint16Array(tris.length * 3);
  tris.forEach((t, i) => {
    out[i * 3] = t[0];
    out[i * 3 + 1] = t[1];
    out[i * 3 + 2] = t[2];
  });
  return out;
}

/** Area-weighted vertex normals. Flips the field if the nose points away. */
export function computeNormals(pos: Float32Array, idx: Uint16Array): Float32Array {
  const n = new Float32Array(pos.length);
  for (let t = 0; t < idx.length; t += 3) {
    const ia = idx[t] * 3;
    const ib = idx[t + 1] * 3;
    const ic = idx[t + 2] * 3;
    const ax = pos[ib] - pos[ia];
    const ay = pos[ib + 1] - pos[ia + 1];
    const az = pos[ib + 2] - pos[ia + 2];
    const bx = pos[ic] - pos[ia];
    const by = pos[ic + 1] - pos[ia + 1];
    const bz = pos[ic + 2] - pos[ia + 2];
    const cx = ay * bz - az * by;
    const cy = az * bx - ax * bz;
    const cz = ax * by - ay * bx;
    n[ia] += cx;
    n[ia + 1] += cy;
    n[ia + 2] += cz;
    n[ib] += cx;
    n[ib + 1] += cy;
    n[ib + 2] += cz;
    n[ic] += cx;
    n[ic + 1] += cy;
    n[ic + 2] += cz;
  }
  // Landmark 1 is the nose tip. It must point toward the camera (+z).
  const flipSign = n[1 * 3 + 2] < 0 ? -1 : 1;
  for (let i = 0; i < n.length; i += 3) {
    const x = n[i] * flipSign;
    const y = n[i + 1] * flipSign;
    const z = n[i + 2] * flipSign;
    const l = Math.hypot(x, y, z) || 1;
    n[i] = x / l;
    n[i + 1] = y / l;
    n[i + 2] = z / l;
  }
  return n;
}

/**
 * Half-width of the face. The chin is much farther from the nose bridge
 * than the cheeks are, so a full radial halo would orbit the chin and
 * shrink the face. Petals use this cheek width instead.
 */
export function faceRadius(pos: Float32Array): number {
  let maxX = 0.45;
  for (let i = 0; i < pos.length; i += 3) {
    maxX = Math.max(maxX, Math.abs(pos[i]));
  }
  return maxX;
}

/** Unique edges of the face tessellation, as line-pair indices. */
export function faceEdges(raw: Uint16Array = FACE_TRIANGLES): Uint16Array {
  const seen = new Set<number>();
  const out: number[] = [];
  const push = (u: number, v: number) => {
    const lo = u < v ? u : v;
    const hi = u < v ? v : u;
    const key = lo * 512 + hi;
    if (seen.has(key)) return;
    seen.add(key);
    out.push(lo, hi);
  };
  for (let i = 0; i < raw.length; i += 3) {
    push(raw[i], raw[i + 1]);
    push(raw[i + 1], raw[i + 2]);
    push(raw[i + 2], raw[i]);
  }
  return new Uint16Array(out);
}

export function selfTestOrient(): void {
  const pos = new Float32Array([0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0]);
  // Second triangle winds against the first across the shared diagonal.
  const raw = new Uint16Array([0, 1, 2, 0, 3, 2]);
  const idx = orientTriangles(pos, raw);
  const n = computeNormals(pos, idx);
  for (let i = 0; i < 4; i++) {
    if (n[i * 3 + 2] < 0.9) {
      throw new Error(`square normal ${i} should point +z, got ${n[i * 3 + 2]}`);
    }
  }
}
