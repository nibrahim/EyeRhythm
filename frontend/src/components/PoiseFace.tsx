/**
 * Poise — a blue face grid beside a top-down bowl.
 *
 * The grid follows the head around the nose bridge and stays until reset.
 * It blinks with the eyes. The balance dial splits every direction into
 * 30° slices: green where the head went most, red where it should go
 * next. It starts all red each day. The ball rolls with the face. The
 * wireframe turns gray until a face returns.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { resetFaceMap } from "../api";
import type { FaceMapState } from "../types";
import { lookAt, multiply, perspective, cameraPosition, type V3 } from "./poiseCamera";
import { faceEdges } from "./poiseMesh";
import {
  BIN_COUNT,
  type BowlAim,
  balanceOf,
  bowlAim,
  decodeBins,
  drawBowl,
  sectorName,
} from "./poiseField";

interface Props {
  map: FaceMapState | null;
  faceFound: boolean;
  eyesClosed: boolean;
  lastBlinkAt: number;
}

const GRID_VERT = `
attribute vec3 aPos;
uniform mat4 uMvp;
void main() {
  gl_Position = uMvp * vec4(aPos, 1.0);
}
`;

const GRID_FRAG = `
precision mediump float;
uniform float uAlpha;
uniform vec3 uColor;
void main() {
  gl_FragColor = vec4(uColor, uAlpha);
}
`;

function compile(gl: WebGLRenderingContext, type: number, source: string): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("shader");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader) || "compile failed";
    gl.deleteShader(shader);
    throw new Error(log);
  }
  return shader;
}

function program(gl: WebGLRenderingContext, vert: string, frag: string): WebGLProgram {
  const p = gl.createProgram();
  if (!p) throw new Error("program");
  gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, vert));
  gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, frag));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
    throw new Error(gl.getProgramInfoLog(p) || "link failed");
  }
  return p;
}

function decodeMesh(b64: string): Float32Array | null {
  if (!b64) return null;
  const bin = atob(b64);
  if (bin.length !== 468 * 3 * 4) return null;
  const copy = new ArrayBuffer(bin.length);
  const bytes = new Uint8Array(copy);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Float32Array(copy);
}

function buffer(gl: WebGLRenderingContext): WebGLBuffer {
  const b = gl.createBuffer();
  if (!b) throw new Error("buffer");
  return b;
}

function upload(
  gl: WebGLRenderingContext,
  target: number,
  buf: WebGLBuffer,
  data: ArrayBufferView,
  usage: number,
) {
  gl.bindBuffer(target, buf);
  gl.bufferData(target, data, usage);
}

interface Slot {
  from: Float32Array;
  to: Float32Array;
  shown: Float32Array;
  key: string;
  t0: number;
  dur: number;
  stamp: number;
}

function emptySlot(): Slot {
  const n = 468 * 3;
  return {
    from: new Float32Array(n),
    to: new Float32Array(n),
    shown: new Float32Array(n),
    key: "",
    t0: 0,
    dur: 50,
    stamp: 0,
  };
}

function sample(slot: Slot, now: number): void {
  const span = slot.dur <= 0 ? 1 : Math.min(1, (now - slot.t0) / slot.dur);
  const shown = slot.shown;
  const from = slot.from;
  const to = slot.to;
  for (let i = 0; i < shown.length; i++) {
    shown[i] = from[i] + (to[i] - from[i]) * span;
  }
}

export function PoiseFace({ map, faceFound, eyesClosed, lastBlinkAt }: Props) {
  const faceRef = useRef<HTMLCanvasElement>(null);
  const dotRef = useRef<HTMLCanvasElement>(null);
  const mapRef = useRef(map);
  const foundRef = useRef(faceFound);
  const eyesRef = useRef(eyesClosed);
  const blinkAtRef = useRef(0);
  const blinkStartRef = useRef(-1e9);
  const [webglOk, setWebglOk] = useState(true);
  const dotsPacked = map?.dots ?? "";
  const balance = useMemo(
    () => balanceOf(decodeBins(dotsPacked) ?? new Float32Array(BIN_COUNT)),
    [dotsPacked],
  );
  mapRef.current = map;
  foundRef.current = faceFound;
  eyesRef.current = eyesClosed;
  if (lastBlinkAt && lastBlinkAt !== blinkAtRef.current) {
    blinkAtRef.current = lastBlinkAt;
    blinkStartRef.current = performance.now();
  }

  useEffect(() => {
    const face = faceRef.current;
    const dots = dotRef.current;
    if (!face || !dots) return;
    const ctx = dots.getContext("2d");
    const gl = face.getContext("webgl", {
      antialias: true,
      alpha: false,
      premultipliedAlpha: false,
    });

    let grid: WebGLProgram | null = null;
    let posBuf: WebGLBuffer | null = null;
    let edgeBuf: WebGLBuffer | null = null;
    let edgeCount = 0;
    if (!gl) {
      setWebglOk(false);
    } else {
      try {
        grid = program(gl, GRID_VERT, GRID_FRAG);
        posBuf = buffer(gl);
        edgeBuf = buffer(gl);
        const edges = faceEdges();
        upload(gl, gl.ELEMENT_ARRAY_BUFFER, edgeBuf, edges, gl.STATIC_DRAW);
        edgeCount = edges.length;
      } catch {
        setWebglOk(false);
        grid = null;
      }
    }

    const slot = emptySlot();
    let alpha = 1;
    let dotKey = "";
    const bars = new Float32Array(BIN_COUNT);
    const trail: BowlAim[] = [];

    const drawFace = (now: number) => {
      if (!gl || !grid || !posBuf || !edgeBuf) return;
      const w = face.clientWidth;
      const h = face.clientHeight;
      if (w < 2 || h < 2) return;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const pw = Math.round(w * dpr);
      const ph = Math.round(h * dpr);
      if (face.width !== pw || face.height !== ph) {
        face.width = pw;
        face.height = ph;
      }
      gl.viewport(0, 0, face.width, face.height);
      gl.clearColor(0.027, 0.043, 0.071, 1);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      const mesh = mapRef.current?.mesh ?? "";
      if (!mesh || edgeCount === 0) {
        slot.key = "";
        return;
      }
      if (mesh !== slot.key) {
        const decoded = decodeMesh(mesh);
        if (decoded) {
          if (!slot.key) {
            slot.from.set(decoded);
            slot.to.set(decoded);
            slot.shown.set(decoded);
            slot.dur = 50;
          } else {
            sample(slot, now);
            slot.from.set(slot.shown);
            slot.to.set(decoded);
            slot.dur = Math.min(160, Math.max(30, now - slot.stamp));
          }
          slot.t0 = now;
          slot.stamp = now;
          slot.key = mesh;
        }
      }
      if (!slot.key) return;
      sample(slot, now);

      const live = foundRef.current;
      let target = 1;
      if (live) {
        target = eyesRef.current ? 0.06 : 1;
        const age = now - blinkStartRef.current;
        if (age >= 0 && age < 180) {
          const dip = Math.sin((age / 180) * Math.PI);
          target = Math.min(target, 1 - 0.92 * dip);
        }
      }
      alpha += (target - alpha) * 0.45;

      gl.enable(gl.DEPTH_TEST);
      gl.disable(gl.CULL_FACE);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      const targetPt: V3 = [0, -0.62, 0];
      const eye = cameraPosition(0, 0.02, 7.2);
      const mvp = multiply(
        perspective((32 * Math.PI) / 180, face.width / face.height, 0.08, 40),
        lookAt(eye, targetPt, [0, 1, 0]),
      );
      gl.useProgram(grid);
      gl.uniformMatrix4fv(gl.getUniformLocation(grid, "uMvp"), false, mvp);
      gl.uniform1f(gl.getUniformLocation(grid, "uAlpha"), Math.max(0, alpha));
      // Blue while a face is in frame. Gray holds the last pose when it is not.
      if (live) gl.uniform3f(gl.getUniformLocation(grid, "uColor"), 0.38, 0.66, 1.0);
      else gl.uniform3f(gl.getUniformLocation(grid, "uColor"), 0.62, 0.64, 0.68);
      upload(gl, gl.ARRAY_BUFFER, posBuf, slot.shown, gl.DYNAMIC_DRAW);
      resetAttribs(gl);
      bindAttrib(gl, grid, "aPos", posBuf, 3);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, edgeBuf);
      gl.drawElements(gl.LINES, edgeCount, gl.UNSIGNED_SHORT, 0);
      gl.disable(gl.BLEND);
    };

    const drawField = (now: number) => {
      if (!ctx) return;
      const w = dots.clientWidth;
      const h = dots.clientHeight;
      if (w < 2 || h < 2) return;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const pw = Math.round(w * dpr);
      const ph = Math.round(h * dpr);
      if (dots.width !== pw || dots.height !== ph) {
        dots.width = pw;
        dots.height = ph;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const packed = mapRef.current?.dots ?? "";
      if (packed && packed !== dotKey) {
        const decoded = decodeBins(packed);
        if (decoded) {
          bars.set(decoded);
          dotKey = packed;
        }
      }

      const current = mapRef.current;
      if (foundRef.current) {
        trail.push(bowlAim(current?.lr ?? 0, current?.up ?? 0, current?.down ?? 0));
        if (trail.length > 16) trail.shift();
      } else {
        trail.length = 0;
      }
      drawBowl(ctx, w, h, bars, trail, now);
    };

    let raf = 0;
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      drawFace(now);
      drawField(now);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      if (gl && grid) gl.getExtension("WEBGL_lose_context")?.loseContext();
    };
  }, []);

  return (
    <div className="poise">
      <canvas ref={faceRef} className="poise__face" aria-hidden hidden={!webglOk} />
      <canvas ref={dotRef} className="poise__field" aria-hidden />
      <div className="poise__legend">
        <div
          className="poise__scale"
          aria-label="Each 30 degree wedge turns green the more you look that way and red where you rarely look. The pulsing wedge is the direction to turn next."
        >
          <span className="poise__key">
            <span className="poise__key-end">rarely</span>
            <span className="poise__key-bar" />
            <span className="poise__key-end">often</span>
          </span>
          <span className="poise__scale-note">
            {balance.least === null || balance.most === null ? (
              "New day: look around to turn the dial green."
            ) : (
              <>
                Most: <b className="poise__most">{sectorName(balance.most)}</b>
                {" · "}Turn more: <b className="poise__least">{sectorName(balance.least)}</b>
              </>
            )}
          </span>
        </div>
        <button
          type="button"
          className="poise__reset"
          onClick={() => {
            void resetFaceMap();
          }}
        >
          Reset
        </button>
      </div>
    </div>
  );
}

function bindAttrib(
  gl: WebGLRenderingContext,
  prog: WebGLProgram,
  name: string,
  buf: WebGLBuffer,
  size: number,
) {
  const loc = gl.getAttribLocation(prog, name);
  if (loc < 0) return;
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0);
}

function resetAttribs(gl: WebGLRenderingContext) {
  const n = gl.getParameter(gl.MAX_VERTEX_ATTRIBS) as number;
  for (let i = 0; i < n; i++) gl.disableVertexAttribArray(i);
}
