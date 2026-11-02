/**
 * Fixed orbit camera for the Poise face.
 *
 * The face mesh stays at the origin. This camera only changes where we
 * look from. yaw 0, pitch 0 sits on +z (the nose points +z). Positive yaw
 * swings the camera toward +x, which is the model's right cheek.
 *
 * Frame check (also run by `selfTestPoiseCamera`):
 *   camera (0, 0, +dist) looks at the origin
 *   world +x projects to screen-right
 *   world +y projects to screen-up
 *   a point on +z stays centered (depth is not a sideways slide)
 */

export type V3 = [number, number, number];

export function cameraPosition(yaw: number, pitch: number, dist: number): V3 {
  const cp = Math.cos(pitch);
  return [dist * Math.sin(yaw) * cp, dist * Math.sin(pitch), dist * Math.cos(yaw) * cp];
}

function sub(a: V3, b: V3): V3 {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function cross(a: V3, b: V3): V3 {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function normalize(a: V3): V3 {
  const l = Math.hypot(a[0], a[1], a[2]) || 1;
  return [a[0] / l, a[1] / l, a[2] / l];
}

function dot(a: V3, b: V3): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

/** Column-major view matrix. `up` must not be parallel to the view direction. */
export function lookAt(eye: V3, target: V3, up: V3): Float32Array {
  const z = normalize(sub(eye, target));
  const x = normalize(cross(up, z));
  const y = cross(z, x);
  const m = new Float32Array(16);
  m[0] = x[0];
  m[1] = y[0];
  m[2] = z[0];
  m[3] = 0;
  m[4] = x[1];
  m[5] = y[1];
  m[6] = z[1];
  m[7] = 0;
  m[8] = x[2];
  m[9] = y[2];
  m[10] = z[2];
  m[11] = 0;
  m[12] = -dot(x, eye);
  m[13] = -dot(y, eye);
  m[14] = -dot(z, eye);
  m[15] = 1;
  return m;
}

/** Column-major perspective. `fovY` is radians. */
export function perspective(
  fovY: number,
  aspect: number,
  near: number,
  far: number,
): Float32Array {
  const f = 1 / Math.tan(fovY / 2);
  const nf = 1 / (near - far);
  const m = new Float32Array(16);
  m[0] = f / Math.max(0.2, aspect);
  m[5] = f;
  m[10] = (far + near) * nf;
  m[11] = -1;
  m[14] = 2 * far * near * nf;
  return m;
}

/** Column-major `a * b` (apply `b` first). */
export function multiply(a: Float32Array, b: Float32Array): Float32Array {
  const o = new Float32Array(16);
  for (let c = 0; c < 4; c++) {
    for (let r = 0; r < 4; r++) {
      o[c * 4 + r] =
        a[r] * b[c * 4] +
        a[4 + r] * b[c * 4 + 1] +
        a[8 + r] * b[c * 4 + 2] +
        a[12 + r] * b[c * 4 + 3];
    }
  }
  return o;
}

/** NDC x, y of a world point. */
export function project(mvp: Float32Array, x: number, y: number, z: number): [number, number] {
  const cx = mvp[0] * x + mvp[4] * y + mvp[8] * z + mvp[12];
  const cy = mvp[1] * x + mvp[5] * y + mvp[9] * z + mvp[13];
  const w = mvp[3] * x + mvp[7] * y + mvp[11] * z + mvp[15];
  return [cx / w, cy / w];
}

export function selfTestPoiseCamera(): void {
  const eye = cameraPosition(0, 0, 4);
  if (Math.abs(eye[0]) > 1e-6 || Math.abs(eye[1]) > 1e-6 || Math.abs(eye[2] - 4) > 1e-6) {
    throw new Error(`front camera should be (0,0,+4), got ${eye.join(",")}`);
  }
  const side = cameraPosition(Math.PI / 2, 0, 4);
  if (side[0] < 3.9 || Math.abs(side[1]) > 1e-6 || Math.abs(side[2]) > 1e-4) {
    throw new Error(`yaw +90° should park the camera on +x, got ${side.join(",")}`);
  }
  const mvp = multiply(
    perspective(Math.PI / 4, 1, 0.1, 50),
    lookAt(eye, [0, 0, 0], [0, 1, 0]),
  );
  const origin = project(mvp, 0, 0, 0);
  const right = project(mvp, 0.6, 0, 0);
  const up = project(mvp, 0, 0.6, 0);
  const closer = project(mvp, 0, 0, 1);
  if (Math.hypot(origin[0], origin[1]) > 1e-4) {
    throw new Error(`origin left the center (${origin.join(",")})`);
  }
  if (right[0] < 0.15) {
    throw new Error(`world +x should be screen-right, got ${right.join(",")}`);
  }
  if (up[1] < 0.15) {
    throw new Error(`world +y should be screen-up, got ${up.join(",")}`);
  }
  if (Math.hypot(closer[0], closer[1]) > 1e-4) {
    throw new Error(`moving toward the camera slid the point (${closer.join(",")})`);
  }
}
