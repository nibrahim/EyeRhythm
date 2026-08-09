/**
 * Full-screen Practice experience.
 *
 * * Countdown — instructions + timer
 * * Active — ball + string thrown from center to extremes (fade fully out)
 * * Summary — session blink rate + regularity for 20s, then auto-close
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { setToggle } from "../api";
import { setPracticeFullscreen } from "../bridge";
import type { EngineState } from "../types";
import { ballPositionAt, CENTER } from "../utils/practicePath";

const BALL_DIAMETER_PX = 40;
const INSTRUCTION =
  "Follow the moving ball with your eyes. A line will connect the center of the screen to the ball. The ball will move to a new position with each beep. Try to follow its movement smoothly without moving your head.";

interface Props {
  state: EngineState;
}

export function PracticeScreen({ state }: Props) {
  const phase = state.practice_phase ?? "off";
  const active =
    Boolean(state.practice) &&
    (phase === "countdown" || phase === "active" || phase === "summary");

  const isCountdown = phase === "countdown";
  const isActive = phase === "active";
  const isSummary = phase === "summary";

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const startPerfRef = useRef(0);
  const startWallRef = useRef(0);

  useEffect(() => {
    if (active) {
      void setPracticeFullscreen(true);
      return () => {
        void setPracticeFullscreen(false);
      };
    }
    void setPracticeFullscreen(false);
  }, [active]);

  useEffect(() => {
    if (isActive && state.practice_active_started_at > 0) {
      const wallMs = state.practice_active_started_at * 1000;
      startWallRef.current = wallMs;
      const elapsedWall = Math.max(0, Date.now() - wallMs);
      startPerfRef.current = performance.now() - elapsedWall;
    }
    if (!isActive) {
      startWallRef.current = 0;
      startPerfRef.current = 0;
    }
  }, [isActive, state.practice_active_started_at]);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el || !active || isSummary) return;
    const ro = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect;
      if (!r) return;
      setSize({
        w: Math.max(1, Math.round(r.width)),
        h: Math.max(1, Math.round(r.height)),
      });
    });
    ro.observe(el);
    const rect = el.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      setSize({
        w: Math.max(1, Math.round(rect.width)),
        h: Math.max(1, Math.round(rect.height)),
      });
    }
    return () => ro.disconnect();
  }, [active, isSummary]);

  const endPractice = useCallback(() => {
    void setToggle("practice", false);
  }, []);

  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        endPractice();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, endPractice]);

  // Active throw animation only.
  useEffect(() => {
    if (!isActive || !active) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    let raf = 0;
    let stopped = false;

    const draw = () => {
      if (stopped) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        raf = requestAnimationFrame(draw);
        return;
      }

      const w = size.w || canvas.clientWidth;
      const h = size.h || canvas.clientHeight;
      if (w < 2 || h < 2) {
        raf = requestAnimationFrame(draw);
        return;
      }

      const intervalS =
        state.practice_interval_s > 0 ? state.practice_interval_s : 3;

      if (startPerfRef.current <= 0 && state.practice_active_started_at > 0) {
        const wallMs = state.practice_active_started_at * 1000;
        startWallRef.current = wallMs;
        const elapsedWall = Math.max(0, Date.now() - wallMs);
        startPerfRef.current = performance.now() - elapsedWall;
      }

      const elapsedS =
        startPerfRef.current > 0
          ? Math.max(0, (performance.now() - startPerfRef.current) / 1000)
          : 0;

      const half = BALL_DIAMETER_PX / 2;
      const marginX = half / w;
      const marginY = half / h;
      const sample = ballPositionAt(elapsedS, intervalS, marginX, marginY);

      const cx = CENTER.x * w;
      const cy = CENTER.y * h;
      const bx = sample.point.x * w;
      const by = sample.point.y * h;
      const r = half;
      const alpha = Math.max(0, Math.min(1, sample.opacity));

      ctx.clearRect(0, 0, w, h);

      // Center anchor (always visible lightly).
      ctx.save();
      ctx.globalAlpha = 0.9;
      ctx.strokeStyle = "rgba(255,255,255,0.12)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx - 14, cy);
      ctx.lineTo(cx + 14, cy);
      ctx.moveTo(cx, cy - 14);
      ctx.lineTo(cx, cy + 14);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(cx, cy, 4, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255,255,255,0.22)";
      ctx.fill();
      ctx.restore();

      // Ball + string only while visible (both disappear together at the corner).
      if (alpha > 0.01) {
        ctx.save();
        ctx.globalAlpha = alpha * 0.85;
        ctx.strokeStyle = "rgba(200, 210, 220, 0.9)";
        ctx.lineWidth = 1.4;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(bx, by);
        ctx.stroke();
        ctx.restore();

        ctx.save();
        ctx.globalAlpha = alpha;
        const grad = ctx.createRadialGradient(
          bx - r * 0.3,
          by - r * 0.35,
          r * 0.12,
          bx,
          by,
          r,
        );
        grad.addColorStop(0, "#b4d6f5");
        grad.addColorStop(0.55, "#5b9fe0");
        grad.addColorStop(1, "#2f78c4");
        ctx.beginPath();
        ctx.arc(bx, by, r, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.shadowColor = `rgba(91, 159, 224, ${0.4 * alpha})`;
        ctx.shadowBlur = 14;
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.strokeStyle = "rgba(255,255,255,0.4)";
        ctx.lineWidth = 1.25;
        ctx.stroke();
        ctx.restore();
      }

      raf = requestAnimationFrame(draw);
    };

    raf = requestAnimationFrame(draw);
    return () => {
      stopped = true;
      cancelAnimationFrame(raf);
    };
  }, [
    isActive,
    active,
    state.practice_interval_s,
    state.practice_active_started_at,
    size.w,
    size.h,
  ]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || size.w < 1 || size.h < 1) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const bw = Math.round(size.w * dpr);
    const bh = Math.round(size.h * dpr);
    if (canvas.width !== bw || canvas.height !== bh) {
      canvas.width = bw;
      canvas.height = bh;
      canvas.style.width = `${size.w}px`;
      canvas.style.height = `${size.h}px`;
    }
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
  }, [size.w, size.h]);

  if (!active) return null;

  const countdownTotal =
    state.practice_countdown_total_s > 0
      ? state.practice_countdown_total_s
      : 20;
  const countdownLeft = Math.max(0, Math.ceil(state.practice_countdown_s));
  const remainingLabel = formatClock(state.practice_remaining_s);
  const summaryLeft = Math.max(0, Math.ceil(state.practice_summary_s ?? 0));
  const resultBpm = state.practice_result_bpm ?? 0;
  const resultReg = state.practice_result_regularity;
  const resultBlinks = state.practice_result_blinks ?? 0;

  return (
    <div
      className="practice-screen"
      role="dialog"
      aria-modal="true"
      aria-label="Practice mode"
    >
      <div className="practice-screen__chrome">
        <div className="practice-screen__brand">EyeRhythm Practice</div>
        <div className="practice-screen__meta">
          {isCountdown ? (
            <span>Starting soon</span>
          ) : isSummary ? (
            <span>Session complete · closing in {summaryLeft}s</span>
          ) : (
            <span title="Time remaining">{remainingLabel}</span>
          )}
        </div>
        <button
          type="button"
          className="practice-screen__end"
          onClick={endPractice}
          title="End practice (Esc)"
        >
          {isSummary ? "Close" : "End practice"}
          <kbd>Esc</kbd>
        </button>
      </div>

      <div className="practice-screen__stage" ref={wrapRef}>
        {isCountdown ? (
          <div className="practice-screen__intro">
            <p className="practice-screen__instruction">{INSTRUCTION}</p>
            <div
              className="practice-screen__countdown"
              aria-live="polite"
              aria-atomic="true"
            >
              <span className="practice-screen__countdown-num">
                {countdownLeft}
              </span>
              <span className="practice-screen__countdown-label">
                seconds until practice begins
              </span>
            </div>
            <div className="practice-screen__countdown-bar" aria-hidden>
              <div
                className="practice-screen__countdown-bar-fill"
                style={{
                  transform: `scaleX(${Math.min(
                    1,
                    Math.max(0, state.practice_countdown_s / countdownTotal),
                  )})`,
                }}
              />
            </div>
          </div>
        ) : isSummary ? (
          <div className="practice-screen__summary" role="status">
            <h2 className="practice-screen__summary-title">Great work</h2>
            <p className="practice-screen__summary-sub">
              Your practice session results
            </p>
            <div className="practice-screen__summary-grid">
              <div className="practice-screen__summary-card">
                <span className="practice-screen__summary-label">
                  Blink rate
                </span>
                <span className="practice-screen__summary-value">
                  {resultBpm > 0 ? resultBpm.toFixed(1) : "0"}
                  <span className="practice-screen__summary-unit">/min</span>
                </span>
                <span className="practice-screen__summary-note">
                  {resultBlinks} blink
                  {resultBlinks === 1 ? "" : "s"} during practice
                </span>
              </div>
              <div className="practice-screen__summary-card">
                <span className="practice-screen__summary-label">
                  Regularity
                </span>
                <span className="practice-screen__summary-value">
                  {resultReg != null ? Math.round(resultReg) : "—"}
                  {resultReg != null ? (
                    <span className="practice-screen__summary-unit">%</span>
                  ) : null}
                </span>
                <span className="practice-screen__summary-note">
                  {resultReg != null
                    ? "inter-blink rhythm score"
                    : "need a few more blinks next time"}
                </span>
              </div>
            </div>
            <div className="practice-screen__countdown-bar practice-screen__countdown-bar--summary" aria-hidden>
              <div
                className="practice-screen__countdown-bar-fill"
                style={{
                  transform: `scaleX(${Math.min(
                    1,
                    Math.max(0, (state.practice_summary_s ?? 0) / 20),
                  )})`,
                }}
              />
            </div>
            <p className="practice-screen__summary-footer">
              Closing automatically in {summaryLeft}s
            </p>
          </div>
        ) : (
          <canvas
            ref={canvasRef}
            className="practice-screen__canvas"
            aria-label="Follow the moving ball with your eyes"
          />
        )}
      </div>

      {isActive ? (
        <div className="practice-screen__hint" aria-hidden>
          Blink gently on each beep · follow the ball with your eyes
        </div>
      ) : null}
    </div>
  );
}

function formatClock(remainingS: number): string {
  const secs = Math.max(0, Math.ceil(remainingS));
  const mm = Math.floor(secs / 60);
  const ss = secs % 60;
  return `${mm}:${ss.toString().padStart(2, "0")}`;
}
