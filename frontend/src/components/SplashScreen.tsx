/**
 * Launch splash: ocular-comfort check, then on-device notices.
 *
 * Stays up until Start is pressed or 3 minutes elapse, whichever is first.
 * The answer is stored only in local preferences (never uploaded).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { savePreferences } from "../api";
import { setSplashLayout, whenBridgeReady } from "../bridge";
import { Logo } from "./Logo";

const SPLASH_LIMIT_MS = 180_000;

export const EYE_COMFORT_OPTIONS = [
  {
    id: "comfortable",
    title: "Comfortable",
    detail: "No dryness, strain, or irritation",
  },
  {
    id: "mild",
    title: "Mild symptoms",
    detail: "Slight dryness or visual fatigue",
  },
  {
    id: "moderate",
    title: "Moderate discomfort",
    detail: "Gritty, burning, or tired eyes",
  },
  {
    id: "marked",
    title: "Marked irritation",
    detail: "Persistent dryness, pain, or light sensitivity",
  },
  {
    id: "decline",
    title: "Prefer not to say",
    detail: "Skip this self-check",
  },
] as const;

export type EyeComfortId = (typeof EYE_COMFORT_OPTIONS)[number]["id"];

const NOTICES = [
  {
    title: "On-device and private",
    body: "EyeRhythm is fully offline in normal use. Camera frames and blink metrics are processed on this computer only — nothing is uploaded, and no internet connection is required. Your ocular data stays with you.",
  },
  {
    title: "A wellness companion, not a medical device",
    body: "EyeRhythm has not been cleared or approved by the FDA or any other regulator. It is not intended to diagnose, treat, cure, or prevent disease. If you have an ocular surface disorder, a change in vision, or persistent discomfort, consult a licensed eye-care professional.",
  },
  {
    title: "Ocular Rhythm Index (ORI)",
    body: "ORI combines blink rate and inter-blink regularity into a 0–100 score of blink cadence during screen use. Reduced blink frequency and incomplete blinking are associated with tear-film instability and digital eye strain. With Alert on, an audible cue can sound if ORI stays below 50 for 3 minutes in the last 5, prompting a healthier blink rhythm.",
  },
] as const;

interface Props {
  onDone: () => void;
}

function formatRemain(ms: number): string {
  const s = Math.max(0, Math.ceil(ms / 1000));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

export function SplashScreen({ onDone }: Props) {
  const [step, setStep] = useState<1 | 2>(1);
  const [comfort, setComfort] = useState<EyeComfortId | null>(null);
  const [remainingMs, setRemainingMs] = useState(SPLASH_LIMIT_MS);

  const doneRef = useRef(false);
  const comfortRef = useRef(comfort);
  const onDoneRef = useRef(onDone);
  comfortRef.current = comfort;
  onDoneRef.current = onDone;

  const finish = useCallback(() => {
    if (doneRef.current) return;
    doneRef.current = true;
    const chosen = comfortRef.current;
    if (chosen) {
      void savePreferences({ eye_comfort: chosen }).catch(() => {
        /* local save is best-effort */
      });
    }
    void setSplashLayout(false).finally(() => {
      onDoneRef.current();
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    void whenBridgeReady().then((ready) => {
      if (!cancelled && ready) void setSplashLayout(true);
    });
    return () => {
      cancelled = true;
      void setSplashLayout(false);
    };
  }, []);

  useEffect(() => {
    const started = performance.now();
    const id = window.setInterval(() => {
      const left = Math.max(0, SPLASH_LIMIT_MS - (performance.now() - started));
      setRemainingMs(left);
      if (left <= 0) finish();
    }, 200);
    return () => window.clearInterval(id);
  }, [finish]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        if (step === 1) {
          if (comfort) setStep(2);
        } else {
          finish();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step, finish, comfort]);

  const progress = remainingMs / SPLASH_LIMIT_MS;

  return (
    <div className="splash" role="dialog" aria-modal="true" aria-labelledby="splash-title">
      <div className="splash__panel">
        <div className="splash__bar" aria-hidden>
          <div
            className="splash__bar-fill"
            style={{ transform: `scaleX(${progress})` }}
          />
        </div>

        <header className="splash__head">
          <Logo size={32} />
          <div className="splash__brand">
            <div id="splash-title" className="splash__title">
              EyeRhythm
            </div>
            <div className="splash__tag">Blink companion</div>
          </div>
          <div className="splash__timer" aria-live="polite">
            {formatRemain(remainingMs)}
          </div>
        </header>

        <div className="splash__body">
          {step === 1 ? (
            <>
              <h2 className="splash__question">
                How would you describe your ocular comfort right now?
              </h2>
              <p className="splash__lead">
                A brief self-check before you begin. This stays on this device
                and is not a diagnosis.
              </p>
              <div
                className="splash__options"
                role="radiogroup"
                aria-label="Current ocular comfort"
              >
                {EYE_COMFORT_OPTIONS.map((opt) => {
                  const active = comfort === opt.id;
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      className={`splash__option${active ? " is-active" : ""}`}
                      onClick={() => setComfort(opt.id)}
                    >
                      <span className="splash__option-dot" />
                      <span className="splash__option-text">
                        <span className="splash__option-title">{opt.title}</span>
                        <span className="splash__option-detail">{opt.detail}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </>
          ) : (
            <>
              <h2 className="splash__question">Before you start</h2>
              <p className="splash__lead">
                Please read these notes. You can begin now, or EyeRhythm will
                continue automatically.
              </p>
              <ol className="splash__notes">
                {NOTICES.map((note, i) => (
                  <li key={note.title} className="splash__note">
                    <span className="splash__note-n" aria-hidden>
                      {i + 1}
                    </span>
                    <div>
                      <div className="splash__note-title">{note.title}</div>
                      <p className="splash__note-body">{note.body}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </>
          )}
        </div>

        <footer className="splash__foot">
          <span className="splash__hint">
            {step === 1
              ? comfort
                ? "Continues automatically in a few minutes"
                : "Choose an option to continue"
              : `Auto-start in ${formatRemain(remainingMs)}`}
          </span>
          {step === 1 ? (
            <button
              type="button"
              className="splash__cta"
              disabled={!comfort}
              onClick={() => setStep(2)}
            >
              Continue
            </button>
          ) : (
            <button type="button" className="splash__cta" onClick={finish}>
              Start
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}
