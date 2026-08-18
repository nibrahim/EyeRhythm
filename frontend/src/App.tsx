import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { fetchPreferences, savePreferences, setToggle } from "./api";
import {
  measureCompactOuterHeight,
  setCompactLayout,
  whenBridgeReady,
} from "./bridge";
import { type AvatarId } from "./components/Avatar";
import { ControlsBar } from "./components/ControlsBar";
import { HeroPanel } from "./components/HeroPanel";
import { Logo } from "./components/Logo";
import { MetricCard } from "./components/MetricCard";
import { InfoQuoteCard } from "./components/InfoQuoteCard";
import { PracticeScreen } from "./components/PracticeScreen";
import { useEngineState } from "./hooks/useEngineState";
import { useRateHistory } from "./hooks/useRateHistory";
import { formatBpm, lookAngleTone, oriTone, regularityTone, rateTone } from "./utils/format";

const AVATARS: AvatarId[] = ["atlas", "lumen", "vesper", "lens", "graph"];

function asAvatarId(v: unknown): AvatarId {
  if (typeof v === "string" && (AVATARS as string[]).includes(v)) {
    return v as AvatarId;
  }
  return "atlas";
}

export default function App() {
  const { state, connected } = useEngineState();
  const [avatarId, setAvatarId] = useState<AvatarId>("atlas");
  const [compact, setCompact] = useState(true);
  const [prefsReady, setPrefsReady] = useState(false);

  // Session-wide Trace history: starts at boot, survives avatar switches + minimize.
  const present = state.face_found && !state.off_screen;
  useRateHistory(state.continuous_bpm, present, state.regularity);

  useEffect(() => {
    void whenBridgeReady();
  }, []);

  // Restore last avatar (and confirm prefs API is up).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const prefs = await fetchPreferences();
        if (!cancelled) {
          setAvatarId(asAvatarId(prefs.avatar));
          const nextCompact = prefs.compact !== false;
          setCompact(nextCompact);
          if (!nextCompact) {
            void setCompactLayout(false);
          }
        }
      } catch {
        /* keep default */
      } finally {
        if (!cancelled) setPrefsReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const persistAvatar = useCallback((id: AvatarId) => {
    setAvatarId(id);
    void savePreferences({ avatar: id }).catch(() => {
      /* offline / restarting */
    });
  }, []);

  const persistCompact = useCallback((next: boolean) => {
    setCompact(next);
    void savePreferences({ compact: next }).catch(() => {
      /* offline / restarting */
    });
    if (!next) {
      void setCompactLayout(false);
    }
  }, []);

  // Hug compact content so the gap under the buttons matches the gap
  // between the title bar and the avatar card.
  useLayoutEffect(() => {
    if (!compact) return;
    let cancelled = false;
    const id = window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        if (cancelled) return;
        const height = measureCompactOuterHeight();
        if (height) void setCompactLayout(true, height);
      });
    });
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(id);
    };
  }, [compact]);

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
      const k = e.key.toLowerCase();
      if (k === "b") void setToggle("beep");
      else if (k === "a") void setToggle("alert");
      else if (k === "t") void setToggle("ontop");
      else if (k === "p") void setToggle("practice");
      else if (k === "d") persistCompact(!compact);
      else if (k === "c") {
        persistAvatar(avatarId === "lens" ? "atlas" : "lens");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [avatarId, compact, persistAvatar, persistCompact]);

  const bpmTone = rateTone(state.continuous_bpm, present);
  const oriValue =
    state.ocular_rhythm_index !== null
      ? Math.round(state.ocular_rhythm_index)
      : "—";
  const oriSub = !present
    ? "no face"
    : state.ocular_rhythm_index === null
      ? "need a few blinks"
      : state.ocular_rhythm_full
        ? "70% rate · 30% rhythm"
        : "rate only · rhythm warming up";
  const oriCardTone = oriTone(state.ocular_rhythm_index, present);
  const regTone = regularityTone(state.regularity);
  const lookTone = lookAngleTone(state.face_angle_deg, state.face_found);

  const regValue =
    state.regularity_ready && state.regularity !== null
      ? Math.round(state.regularity)
      : "—";
  const regSub = state.regularity_ready
    ? "inter-blink rhythm"
    : state.regularity_gaps > 0
      ? `warming up · ${state.regularity_gaps}/2 gaps`
      : "need a few blinks";

  const lookValue =
    state.face_found && state.face_angle_deg !== null
      ? Math.round(state.face_angle_deg)
      : "—";
  const lookSub = !state.face_found
    ? "no face"
    : state.off_screen
      ? "off-screen"
      : state.face_direction || "straight";

  return (
    <div
      className={`app-shell${compact ? " is-compact" : ""}`}
      data-prefs-ready={prefsReady ? "1" : "0"}
    >
      <header className="topbar">
        <div className="topbar__brand">
          <Logo size={30} />
          <div>
            <div className="topbar__title">EyeRhythm</div>
            <div className="topbar__tag">Blink companion</div>
          </div>
        </div>
        <div className="topbar__status">
          <span
            className={`status-dot ${
              connected && state.camera_ok
                ? "ok"
                : connected
                  ? "warn"
                  : "bad"
            }`}
          />
          <span className="status-text">
            {!connected
              ? "Connecting…"
              : state.camera_ok
                ? "Live"
                : state.camera_message || "Camera"}
          </span>
        </div>
      </header>

      <main className="dashboard">
        <HeroPanel
          state={state}
          avatarId={avatarId}
          onAvatarChange={persistAvatar}
        />

        <button
          type="button"
          className="layout-toggle"
          onClick={() => persistCompact(!compact)}
          title={
            compact
              ? "Show rates, screen time and other cards (D)"
              : "Hide extra cards and shrink the window (D)"
          }
        >
          <span>{compact ? "More" : "Less"}</span>
          <span className="layout-toggle__chevron" aria-hidden>
            {compact ? "▾" : "▴"}
          </span>
        </button>

        <div className="target-strip" role="note" hidden={compact}>
          <span className="target-strip__label">Target rhythm</span>
          <span className="target-strip__value">
            ≈ 15–20 blinks/min while working
          </span>
        </div>

        <section
          className="metrics-grid"
          aria-label="Blink metrics"
          hidden={compact}
        >
          <MetricCard
            title="Continuous rate"
            value={formatBpm(state.continuous_bpm)}
            unit="/min"
            subtitle="last ~60s"
            tone={bpmTone}
            palette="sage"
          />
          <MetricCard
            title="Ocular Rhythm Index"
            value={oriValue}
            unit={state.ocular_rhythm_index !== null ? "/100" : undefined}
            subtitle={oriSub}
            tone={oriCardTone}
            palette="mint"
          />
          <MetricCard
            title="Screen time"
            value={state.screen_time}
            subtitle="face visible today"
            tone="neutral"
            palette="peach"
          />
          <MetricCard
            title="FPS"
            value={state.fps > 0 ? state.fps.toFixed(0) : "—"}
            subtitle="camera pipeline"
            tone="neutral"
            palette="sky"
          />
          <MetricCard
            title="Regularity"
            value={regValue}
            unit={state.regularity_ready ? "/100" : undefined}
            subtitle={regSub}
            tone={regTone}
            palette="sun"
          />
          <MetricCard
            title="Look angle"
            value={lookValue}
            unit={
              state.face_found && state.face_angle_deg !== null ? "°" : undefined
            }
            subtitle={lookSub}
            tone={lookTone}
            palette="lavender"
          />
          {/* Always full-width gray card: tips + famous quotes (practice mode overlays coach) */}
          <InfoQuoteCard
            practice={Boolean(state.practice)}
            practicePhase={state.practice_phase ?? "off"}
            countdownS={state.practice_countdown_s ?? 0}
            remainingS={state.practice_remaining_s ?? 0}
          />
        </section>
      </main>

      <div className="shell-footer">
        <ControlsBar state={state} />
      </div>

      {/* Full-screen practice: countdown + ball/string visual coach */}
      <PracticeScreen state={state} />
    </div>
  );
}
